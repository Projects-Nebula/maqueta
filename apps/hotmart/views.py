"""Hotmart connect/disconnect views + page shell (see openspec design:
hotmart-developer-credentials-pivot, "Data Flow" section). No credential
or token value ever reaches a template, response body, or log line — see
design doc's Security Approach and the spec's Encrypted Storage
requirement.
"""

from __future__ import annotations

import logging
import time

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.ai_assistant.document_validation import DocumentValidationError
from apps.ai_assistant.providers import AIProviderError, AIProviderTimeout
from apps.ai_assistant.sse import first_error, sse_event
from apps.ai_assistant.usage_logging import log_ai_usage
from apps.ai_assistant.wizard_service import WizardAIService
from apps.editor.models import AuditEvent, UserTemplate
from apps.editor.palettes import get_palette_preset, user_palette_for_client

from .client import HotmartClientError, build_hotmart_client
from .models import HotmartConnection, HotmartProductLink
from .seeding import build_generation_seed
from .serializers import (
    HotmartCredentialsSerializer,
    HotmartProductLinkSerializer,
    LandingGenerateRequestSerializer,
)
from .services import HotmartReconnectRequired, ensure_fresh_token, reconcile_products

logger = logging.getLogger(__name__)


@login_required
def connection_view(request):
    """/hotmart/ — connection status page shell. All CRUD happens
    client-side against /api/hotmart/* (static/hotmart/connection.js):
    the credential paste form POSTs to CredentialsView, disconnect POSTs to
    DisconnectView. The catalog/link UI lands in a later PR; this shell
    only shows connect/disconnect for now."""
    connection = HotmartConnection.objects.filter(owner=request.user).first()
    connected = connection is not None and connection.has_credentials()
    return render(request, "hotmart/connection.html", {"connected": connected})


class CredentialsView(APIView):
    """POST /api/hotmart/credentials/ — validate-before-persist (design:
    "validate against Hotmart before persisting; no 'unverified' state").
    Builds a throwaway real client from the submitted pair, calls
    `fetch_token()`, and only on success persists the encrypted
    credentials AND the returned access token. A blank field keeps the
    corresponding stored value (spec: "Rotating one credential")."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = HotmartCredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        connection = HotmartConnection.objects.filter(owner=request.user).first()
        existing = connection.get_credentials() if connection else {}

        client_id = serializer.validated_data["client_id"] or existing.get("client_id", "")
        client_secret = serializer.validated_data["client_secret"] or existing.get(
            "client_secret", ""
        )

        if not client_id or not client_secret:
            return Response({"ok": False, "error": "invalid_credentials"}, status=400)

        client = build_hotmart_client({"client_id": client_id, "client_secret": client_secret})
        try:
            tokens = client.fetch_token()
        except HotmartClientError:
            logger.warning("hotmart credential validation failed")
            return Response({"ok": False, "error": "invalid_credentials"}, status=400)

        if connection is None:
            connection = HotmartConnection(owner=request.user)
        connection.set_credentials({"client_id": client_id, "client_secret": client_secret})
        connection.set_tokens(access=tokens.access_token, expires_in=tokens.expires_in)
        connection.save()

        return Response(
            {
                "connected": True,
                "has_credentials": {
                    "client_id": bool(client_id),
                    "client_secret": bool(client_secret),
                },
            }
        )


class DisconnectView(APIView):
    """POST /api/hotmart/disconnect/ — deletes the connection row
    (cascades any product links). Owner-scoped via request.user, same
    IsAuthenticated contract as the rest of the design's API surface."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        HotmartConnection.objects.filter(owner=request.user).delete()
        return Response(status=204)


class ProductListView(APIView):
    """GET /api/hotmart/products/ — live catalog proxy (spec: "Server-Side
    Product Listing"). Never returns a token; also drives the opportunistic
    reconciliation sync on every authenticated fetch (design: "sync =
    shared reconcile function, two triggers")."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        connection = HotmartConnection.objects.filter(owner=request.user).first()
        if connection is None:
            return Response({"connected": False, "products": []})

        client = build_hotmart_client(connection.get_credentials())
        try:
            access_token = ensure_fresh_token(connection, client)
        except HotmartReconnectRequired:
            return Response({"connected": True, "error": "reconnect_required"}, status=409)

        try:
            products = client.list_products(access_token)
        except HotmartClientError:
            logger.exception("hotmart product list request failed")
            reconcile_products(connection, None)
            return Response({"connected": True, "products": [], "error": "upstream_unavailable"})

        reconcile_products(connection, products)
        linked_ids = set(connection.product_links.values_list("hotmart_product_id", flat=True))
        return Response(
            {
                "connected": True,
                "products": [
                    {
                        "id": product.id,
                        "ucode": product.ucode,
                        "name": product.name,
                        "is_active": product.is_active,
                        "checkout_url": product.checkout_url,
                        "linked": product.id in linked_ids,
                    }
                    for product in products
                ],
            }
        )


class ProductLinkViewSet(viewsets.ModelViewSet):
    """Owner-scoped CRUD for /api/hotmart/links/ (spec: "One-to-One
    Product-Landing Link"). Unlinking is metadata-only — DELETE never
    calls unpublish() on the landing (design: "Metadata-Only Linking")."""

    serializer_class = HotmartProductLinkSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        return HotmartProductLink.objects.filter(connection__owner=self.request.user)

    def _connection(self):
        return get_object_or_404(HotmartConnection, owner=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in ("create", "update", "partial_update"):
            context["connection"] = self._connection()
        return context

    def perform_create(self, serializer):
        serializer.save(connection=self._connection())


class ProductLandingGenerateView(APIView):
    """POST /api/hotmart/products/<product_id>/generate/ — SSE (see design:
    ai-landing-from-hotmart-product, "Orchestrating view lives in
    apps/hotmart"). Fetches the product + its main offer, builds a seed
    from them plus the seller's 3 fixed answers, runs the UNCHANGED wizard
    generation pipeline (`WizardAIService.stream_generate_document`), then
    atomically creates-or-updates the linked `UserTemplate` +
    `HotmartProductLink`.

    The ACTIVE-status gate is enforced here by re-fetching `list_products`
    (design: "ACTIVE gate enforced server-side") — this also authenticates
    that the product belongs to *this* connection's catalog and yields the
    `ucode` needed for `list_offers`. The product id is untrusted input;
    a client-supplied `is_active` flag is a UX affordance only.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hotmart_landing_generate"

    def post(self, request, product_id):
        serializer = LandingGenerateRequestSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            logger.warning(
                "hotmart landing generate invalid input for user %s: %s",
                request.user.pk,
                serializer.errors,
            )
            return Response(
                {"error": "invalid_input", "detail": first_error(serializer.errors)},
                status=400,
            )
        data = serializer.validated_data
        user_id = request.user.pk
        scope = self.throttle_scope

        connection = HotmartConnection.objects.filter(owner=request.user).first()
        if connection is None:
            return Response({"error": "reconnect_required"}, status=409)

        client = build_hotmart_client(connection.get_credentials())
        try:
            access_token = ensure_fresh_token(connection, client)
        except HotmartReconnectRequired:
            return Response({"error": "reconnect_required"}, status=409)

        try:
            products = client.list_products(access_token)
        except HotmartClientError:
            logger.exception("hotmart product list request failed during landing generation")
            return Response({"error": "upstream_unavailable"}, status=502)

        product = next((p for p in products if p.id == product_id), None)
        if product is None:
            return Response({"error": "product_not_found"}, status=404)
        if not product.is_active:
            return Response({"error": "product_not_active"}, status=400)

        try:
            offers = client.list_offers(access_token, product.ucode)
        except HotmartClientError:
            logger.exception("hotmart offer list request failed during landing generation")
            return Response({"error": "upstream_unavailable"}, status=502)
        offer = offers[0] if offers else None

        description, seed_answers = build_generation_seed(product, offer, data["answers"])

        palette_id = data.get("palette_id")
        selected_palette = get_palette_preset(palette_id)
        if selected_palette is None and palette_id:
            user_palette = request.user.user_palettes.filter(slug=palette_id).first()
            if user_palette is None:
                return Response({"error": "invalid_input", "detail": "unknown palette"}, status=400)
            selected_palette = user_palette_for_client(user_palette)

        checkout_url = data.get("checkout_url", "")
        assets = data.get("assets", [])

        def event_stream():
            start_time = time.monotonic()
            outcome = "success"
            try:
                for kind, value in WizardAIService().stream_generate_document(
                    description,
                    seed_answers,
                    [],
                    assets=assets,
                    palette_id=palette_id,
                    selected_palette=selected_palette,
                ):
                    if kind == "reasoning":
                        yield sse_event("reasoning", {"text": value})
                        continue

                    # Transaction lives INSIDE the generator, wrapping only
                    # the persistence step (design decision: StreamingHttpResponse
                    # runs this generator after post() already returned, so a
                    # view-level atomic block would commit before the AI call
                    # even starts and hold a connection across it).
                    with transaction.atomic():
                        link = HotmartProductLink.objects.filter(
                            connection=connection, hotmart_product_id=product.id
                        ).first()
                        if link is not None:
                            # Regenerate: update the existing UserTemplate in
                            # place — preserves pk/public_slug/is_published
                            # and any FK'd analytics/revision records.
                            template = link.user_template
                            template.name = value.name
                            template.state = value.state
                            template.save(update_fields=["name", "state", "updated_at"])
                            link.product_name = product.name
                            if checkout_url:
                                link.checkout_url = checkout_url
                            link.status = HotmartProductLink.Status.ACTIVE
                            link.save(
                                update_fields=[
                                    "product_name",
                                    "checkout_url",
                                    "status",
                                    "updated_at",
                                ]
                            )
                        else:
                            template = UserTemplate.objects.create(
                                owner=request.user, name=value.name, state=value.state
                            )
                            link = HotmartProductLink.objects.create(
                                connection=connection,
                                user_template=template,
                                hotmart_product_id=product.id,
                                product_name=product.name,
                                checkout_url=checkout_url,
                            )
                        AuditEvent.record(
                            owner=request.user,
                            action=AuditEvent.Action.AI_WIZARD_GENERATE,
                            target_type="editor_session",
                            metadata={"name": value.name, "source": "hotmart"},
                        )

                    yield sse_event(
                        "done",
                        {
                            "template_id": template.id,
                            "link_id": link.id,
                            "name": value.name,
                            "summary": value.summary,
                            "editor_url": f"{reverse('editor:editor')}?ut={template.id}",
                        },
                    )
            except AIProviderTimeout:
                outcome = "ai_timeout"
                logger.warning("hotmart landing generate timed out for user %s", user_id)
                yield sse_event("error", {"error": "ai_timeout"})
            except AIProviderError:
                outcome = "ai_unavailable"
                logger.exception("hotmart landing generate provider error for user %s", user_id)
                yield sse_event("error", {"error": "ai_unavailable"})
            except DocumentValidationError:
                outcome = "invalid_document"
                logger.warning(
                    "hotmart landing generate produced an invalid document for user %s", user_id
                )
                yield sse_event("error", {"error": "invalid_document"})
            except Exception:
                outcome = "unexpected_error"
                logger.exception(
                    "Unexpected error during hotmart landing generate for user %s", user_id
                )
                yield sse_event("error", {"error": "unexpected_error"})
            finally:
                log_ai_usage(scope, user_id, outcome, start_time)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
