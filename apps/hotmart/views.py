"""Hotmart connect/disconnect views + page shell (see openspec design:
hotmart-developer-credentials-pivot, "Data Flow" section). No credential
or token value ever reaches a template, response body, or log line — see
design doc's Security Approach and the spec's Encrypted Storage
requirement.
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .client import HotmartClientError, build_hotmart_client
from .models import HotmartConnection, HotmartProductLink
from .oauth import build_authorize_url, issue_state
from .serializers import HotmartCredentialsSerializer, HotmartProductLinkSerializer
from .services import HotmartReconnectRequired, ensure_fresh_token, reconcile_products

logger = logging.getLogger(__name__)


@login_required
def connection_view(request):
    """/hotmart/ — connection status page shell. All CRUD happens
    client-side against /api/hotmart/* (static/hotmart/connection.js).
    The catalog/link UI lands in a later PR; this shell only shows
    connect/disconnect for now."""
    connected = HotmartConnection.objects.filter(owner=request.user).exists()
    return render(request, "hotmart/connection.html", {"connected": connected})


@login_required
@require_http_methods(["GET"])
def connect_view(request):
    """/hotmart/conectar/ — issues a signed, session-bound, single-use
    state and redirects to Hotmart's authorize endpoint. There is no
    next/return_to param anywhere in this flow (design ADR: the
    post-callback destination is a hardcoded reverse())."""
    state = issue_state(request)
    authorize_url = build_authorize_url(request, state)
    return HttpResponseRedirect(authorize_url)


@login_required
@require_http_methods(["GET"])
def callback_view(request):
    """/hotmart/callback/ — STUBBED to 410 Gone (PR A of the
    developer-credentials pivot). The `authorization_code` exchange this
    view used to perform is no longer reachable now that
    `build_hotmart_client()` requires per-seller Developer Credentials;
    stubbing (rather than deleting) keeps `main` from carrying a
    live-but-broken exchange path mid-stack. PR B deletes this view, along
    with `connect_view` and `oauth.py`, once the paste-credential form
    ships (see design's "Migration / Rollout" delivery note)."""
    return HttpResponse(status=410)


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
