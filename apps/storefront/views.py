import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Order, Product
from .payments import PaymentProviderError, build_payment_provider
from .serializers import ProductSerializer

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@login_required
def products_view(request):
    """/productos/ — the owner's product list/management page. A plain
    server-rendered shell; all CRUD happens client-side against
    /api/products/ (static/storefront/products.js)."""
    return render(request, "storefront/products.html", {})


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutView(APIView):
    """POST /comprar/<product_id>/ — creates a Stripe Checkout Session and
    redirects to it. Never trusts a price/currency/name from the request —
    only the product id; everything charged comes from the DB row
    (FEATURE.md 1.6). CSRF-exempt: an anonymous buyer has no CSRF cookie to
    present; integrity comes from the server-side product lookup, not a
    form token. authentication_classes=[]: DRF's SessionAuthentication runs
    its OWN CSRF check independent of csrf_exempt whenever it successfully
    authenticates a request — a logged-in visitor (e.g. the template's own
    owner, testing their own buy button) would otherwise still get a CSRF
    403 despite the decorator above. Not a problem here: permission_classes
    is already AllowAny, so there's no reason to authenticate the requester
    at all for this public, unauthenticated action.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout_session_create"

    def post(self, request, product_id):
        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if not product:
            raise Http404

        success_url = (
            request.build_absolute_uri(reverse("storefront:success"))
            + "?session_id={CHECKOUT_SESSION_ID}"
        )
        cancel_url = request.build_absolute_uri(reverse("storefront:checkout-cancel"))

        provider = build_payment_provider(settings)
        try:
            session = provider.create_checkout_session(
                product_name=product.name,
                amount_cents=product.price_cents,
                currency=settings.DEFAULT_CURRENCY,
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(product.id),
            )
        except PaymentProviderError:
            logger.exception("checkout session creation failed for product %s", product_id)
            return Response({"error": "checkout_unavailable"}, status=502)

        return HttpResponseRedirect(session.url)


def checkout_cancel_view(request):
    return render(request, "storefront/checkout_cancel.html", {})


class SuccessView(APIView):
    """GET /gracias/?session_id=... — the buyer lands here after Stripe
    Checkout. The webhook (StripeWebhookView) is delivered asynchronously
    and may not have created/updated the Order yet by the time this loads
    (FEATURE.md 1.6b) — fall back to a direct provider lookup instead of
    assuming the Order already exists.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        session_id = request.GET.get("session_id")
        if not session_id:
            raise Http404

        order = Order.objects.filter(stripe_session_id=session_id).first()
        if order and order.status == Order.Status.PAID:
            return render(
                request,
                "storefront/success.html",
                {"order": order, "download_url": _download_url(request, order)},
            )

        # Webhook hasn't landed yet (or never will for this session) — ask
        # the provider directly rather than showing a false negative.
        provider = build_payment_provider(settings)
        try:
            status = provider.retrieve_session(session_id)
        except PaymentProviderError:
            return render(request, "storefront/success.html", {"pending": True})

        if status.payment_status != "paid":
            return render(request, "storefront/success.html", {"pending": True})

        # Paid per Stripe, but our webhook hasn't recorded it yet — do not
        # fabricate an Order here (that's the webhook's job alone, 1.7);
        # tell the buyer to wait rather than showing a download link for a
        # purchase our own database doesn't yet know about.
        return render(request, "storefront/success.html", {"pending": True})


def _download_url(request, order):
    if not order.download_token:
        return None
    return request.build_absolute_uri(
        reverse("storefront:download", kwargs={"token": order.download_token})
    )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """POST /webhooks/stripe/ — the ONLY place an Order is created. Never
    rate-limited (a dropped legitimate webhook silently loses an order) and
    never CSRF-checked (Stripe can't present a token) — authenticity comes
    entirely from signature verification. authentication_classes=[]: see
    CheckoutView's docstring — SessionAuthentication's own CSRF check is
    independent of csrf_exempt, and there's no legitimate requester to
    authenticate here anyway (Stripe, not a browser session).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        provider = build_payment_provider(settings)
        try:
            event = provider.parse_webhook_event(
                payload=request.body,
                sig_header=request.META.get("HTTP_STRIPE_SIGNATURE", ""),
                webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except PaymentProviderError:
            logger.warning("rejected webhook with invalid signature")
            return Response(status=400)

        event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
        if event_type != "checkout.session.completed":
            return Response(status=200)

        session_obj = (
            event.get("data", {}).get("object", {})
            if isinstance(event, dict)
            else event["data"]["object"]
        )
        session_id = session_obj.get("id") if isinstance(session_obj, dict) else session_obj["id"]

        try:
            status = provider.retrieve_session(session_id)
        except PaymentProviderError:
            logger.exception("could not retrieve session %s for webhook processing", session_id)
            return Response(status=502)

        product_id = (
            session_obj.get("client_reference_id") if isinstance(session_obj, dict) else None
        )
        product = Product.objects.filter(pk=product_id).first() if product_id else None
        order_status = Order.Status.PAID if status.payment_status == "paid" else Order.Status.FAILED

        order, created = Order.objects.get_or_create(
            stripe_session_id=session_id,
            defaults={
                "product": product,
                "buyer_email": status.customer_email,
                "amount_cents": status.amount_total,
                "currency": status.currency,
                "status": order_status,
            },
        )
        if created and order.status == Order.Status.PAID and product and product.digital_file:
            order.download_token = Order.generate_download_token()
            order.save(update_fields=["download_token"])

        return Response(status=200)


class DownloadView(APIView):
    """GET /descargas/<token>/ — serves a paid order's digital_file. Same
    404-for-everything posture as the public template view: wrong token,
    unpaid order, no digital file, or exhausted download cap all 404 —
    never distinguish which."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "digital_download"

    def get(self, request, token):
        order = Order.objects.filter(download_token=token, status=Order.Status.PAID).first()
        if not order or not order.product or not order.product.digital_file:
            raise Http404
        if order.download_count >= order.max_downloads:
            raise Http404

        order.download_count += 1
        order.save(update_fields=["download_count"])
        return FileResponse(
            order.product.digital_file.open("rb"),
            as_attachment=True,
            filename=order.product.digital_file.name.rsplit("/", 1)[-1],
        )
