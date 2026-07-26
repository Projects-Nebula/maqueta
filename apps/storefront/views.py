import logging
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Order, PaymentGatewayConfig, Product
from .payments import GATEWAY_REGISTRY, PaymentProviderError, build_payment_provider
from .serializers import PaymentGatewayConfigSerializer, ProductSerializer

logger = logging.getLogger(__name__)


def _gateway_config_for(owner_id, gateway):
    return PaymentGatewayConfig.objects.filter(owner_id=owner_id, gateway=gateway).first()


def _provider_for(owner_id, gateway):
    """Builds the provider a checkout/webhook for this owner+gateway should
    use — real if enabled with complete credentials, otherwise that
    gateway's own Fake variant (see payments.build_payment_provider)."""
    config = _gateway_config_for(owner_id, gateway)
    credentials = config.get_credentials() if config else None
    return build_payment_provider(gateway, credentials)


def _send_order_confirmation(order):
    """Best-effort receipt email — never let a delivery failure break the
    checkout flow the buyer is actively waiting on."""
    if not order.buyer_email:
        return
    try:
        send_mail(
            subject="Confirmación de tu compra",
            message=(
                f"Gracias por tu compra{' de ' + order.product.name if order.product else ''}.\n"
                f"Monto: {order.amount_cents / 100:.2f} {order.currency.upper()}\n"
                f"Referencia: {order.gateway_session_id}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.buyer_email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("order confirmation email failed for order %s", order.pk)


def _record_order_for_session(provider, gateway, session_id, product_id):
    """Create (or no-op if already created) the Order for a paid session.

    The single source of truth for "a session was paid" — normally reached
    only via a gateway's real, signature-verified webhook view.
    CheckoutView also calls this directly, but ONLY when running against a
    Fake* provider: there is no real payment server in dev/test to ever
    deliver a webhook, so without this a fake provider's "instantly-
    successful payment" (payments.py) would leave the buyer stuck on
    "Procesando tu pago..." forever, since nothing else would ever create
    the Order row. Never called this way for a real provider — real
    payments still require the actual signed webhook. Raises
    PaymentProviderError on lookup failure — callers decide what HTTP
    status that becomes.
    """
    status = provider.retrieve_session(session_id)

    product = Product.objects.filter(pk=product_id).first() if product_id else None
    order_status = Order.Status.PAID if status.payment_status == "paid" else Order.Status.FAILED

    order, created = Order.objects.get_or_create(
        gateway=gateway,
        gateway_session_id=session_id,
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
    if created and order.status == Order.Status.PAID:
        _send_order_confirmation(order)


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


@login_required
def payment_config_view(request):
    """/config/ — the owner's payment-gateway configuration page (enable
    each of the 8 gateways, paste in credentials). Plain server-rendered
    shell; all CRUD happens client-side against
    /api/payment-gateway-configs/ (static/storefront/payment-config.js)."""
    return render(request, "storefront/payment_config.html", {})


class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):
    """Owner-scoped CRUD for /api/payment-gateway-configs/. Credentials are
    write-only (see the serializer) — never returned in any response, even
    to the owner who set them; the UI shows only whether each field is
    already set, never its value, once saved."""

    serializer_class = PaymentGatewayConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PaymentGatewayConfig.objects.filter(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        """Validate stored credentials without creating a payment session."""
        config = self.get_object()
        required_fields, real_factory, _fake_factory = GATEWAY_REGISTRY[config.gateway]
        credentials = config.get_credentials()
        missing = [field for field in required_fields if not credentials.get(field)]
        if missing:
            return Response(
                {
                    "ok": False,
                    "error": "missing_credentials",
                    "missing": missing,
                },
                status=400,
            )
        try:
            real_factory(credentials)
        except Exception:
            logger.warning("payment credentials could not initialize for %s", config.gateway)
            return Response(
                {"ok": False, "error": "invalid_credentials"},
                status=400,
            )
        return Response({"ok": True, "message": "Credentials are complete and ready."})

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


def _gateway_display_names():
    return {
        "stripe": "Stripe",
        "mercadopago": "Mercado Pago",
        "paypal": "PayPal",
        "braintree": "Braintree",
        "wompi": "Wompi",
        "payu": "PayU",
        "epayco": "ePayco",
        "bold": "Bold",
    }


def enabled_gateways_for(owner_id) -> list[dict]:
    """Every gateway this owner has explicitly enabled — used to render one
    "Pagar con X" button per gateway on a product card (apps/ai_assistant's
    available_gateways context, see prompts.py)."""
    names = _gateway_display_names()
    return [
        {"gateway": config.gateway, "label": names.get(config.gateway, config.gateway)}
        for config in PaymentGatewayConfig.objects.filter(owner_id=owner_id, is_enabled=True)
    ]


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutView(APIView):
    """POST /comprar/<product_id>/<gateway>/ — creates a checkout session
    with the product owner's configured gateway and redirects to it. Never
    trusts a price/currency/name from the request — only the product id;
    everything charged comes from the DB row (FEATURE.md 1.6). CSRF-exempt:
    an anonymous buyer has no CSRF cookie to present; integrity comes from
    the server-side product lookup, not a form token.
    authentication_classes=[]: DRF's SessionAuthentication runs its OWN CSRF
    check independent of csrf_exempt whenever it successfully authenticates
    a request — a logged-in visitor (e.g. the template's own owner, testing
    their own buy button) would otherwise still get a CSRF 403 despite the
    decorator above. Not a problem here: permission_classes is already
    AllowAny, so there's no reason to authenticate the requester at all for
    this public, unauthenticated action.

    `gateway` is optional (see the `checkout-legacy` URL): a buy button
    baked into a UserTemplate's saved state from before the multi-gateway
    checkout shipped still points at `/comprar/<id>/` with no gateway
    segment — rather than 404ing an already-published page's button, fall
    back to the seller's first enabled gateway (deterministic order).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout_session_create"

    def post(self, request, product_id, gateway=None):
        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if not product:
            raise Http404
        if gateway is None:
            fallback = (
                PaymentGatewayConfig.objects.filter(owner_id=product.owner_id, is_enabled=True)
                .order_by("gateway")
                .first()
            )
            if not fallback:
                return self._deliver_for_free(request, product)
            gateway = fallback.gateway
        if gateway not in GATEWAY_REGISTRY:
            raise Http404
        config = _gateway_config_for(product.owner_id, gateway)
        if not config or not config.is_enabled:
            # The seller never turned this gateway on for their shop —
            # never let it be reachable, same "don't offer what isn't
            # actually configured" posture as everything else here.
            raise Http404

        success_url = (
            request.build_absolute_uri(reverse("storefront:success"))
            + f"?gateway={gateway}&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = request.build_absolute_uri(reverse("storefront:checkout-cancel"))

        provider = build_payment_provider(gateway, config.get_credentials())
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
            logger.exception(
                "checkout session creation failed for product %s via %s", product_id, gateway
            )
            return Response({"error": "checkout_unavailable"}, status=502)

        is_fake = type(provider).__name__.startswith("Fake")
        if is_fake:
            # No real payment server exists in dev/test to ever deliver the
            # webhook — record the order immediately, matching what the
            # fake provider already pretends happened (an instantly-
            # successful payment). Real gateway checkouts never take this path.
            try:
                _record_order_for_session(provider, gateway, session.id, str(product.id))
            except PaymentProviderError:
                logger.exception("could not record fake order for session %s", session.id)

        return HttpResponseRedirect(session.url)

    def _deliver_for_free(self, request, product):
        """The seller has no gateway enabled at all — deliver the product
        directly instead of 404ing, but still record a real, permanent
        Order (amount_cents=0, gateway="none") so a $0 delivery is
        auditable exactly like a real purchase, never silently untracked."""
        session_id = f"free_{uuid.uuid4().hex}"
        order = Order.objects.create(
            product=product,
            gateway=Order.Gateway.NONE,
            gateway_session_id=session_id,
            amount_cents=0,
            currency=settings.DEFAULT_CURRENCY,
            status=Order.Status.PAID,
        )
        if product.digital_file:
            order.download_token = Order.generate_download_token()
            order.save(update_fields=["download_token"])
        success_url = (
            request.build_absolute_uri(reverse("storefront:success"))
            + f"?gateway={Order.Gateway.NONE}&session_id={session_id}"
        )
        return HttpResponseRedirect(success_url)


def checkout_cancel_view(request):
    return render(request, "storefront/checkout_cancel.html", {})


class SuccessView(APIView):
    """GET /gracias/?gateway=...&session_id=... — the buyer lands here
    after checkout. The gateway's webhook is delivered asynchronously and
    may not have created/updated the Order yet by the time this loads
    (FEATURE.md 1.6b) — fall back to a direct provider lookup instead of
    assuming the Order already exists. Some gateways (PayU, ePayco) have no
    simple "retrieve by reference" call at all — for those this always
    falls through to "pending" until their webhook actually lands, which is
    the correct/only way those two can be confirmed.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        gateway = request.GET.get("gateway", "")
        session_id = request.GET.get("session_id")
        if not session_id or (gateway != Order.Gateway.NONE and gateway not in GATEWAY_REGISTRY):
            raise Http404

        order = Order.objects.filter(gateway=gateway, gateway_session_id=session_id).first()
        if order and order.status == Order.Status.PAID:
            return render(
                request,
                "storefront/success.html",
                {"order": order, "download_url": _download_url(request, order)},
            )

        # Webhook hasn't landed yet (or never will for this session) — ask
        # the provider directly rather than showing a false negative. We
        # don't know the product owner here (no product id on this URL), so
        # this can only use the fake provider's own class-level session
        # store, or (for real gateways) a lookup that doesn't require
        # per-owner credentials in the first place — PayPal/Mercado
        # Pago/Wompi's retrieve_session needs real credentials, so this
        # fallback is best-effort and mainly exercises the fake-provider
        # dev path exactly like it already did for Stripe-only.
        try:
            provider = build_payment_provider(gateway, None)
            status = provider.retrieve_session(session_id)
        except PaymentProviderError:
            return render(request, "storefront/success.html", {"pending": True})

        if status.payment_status != "paid":
            return render(request, "storefront/success.html", {"pending": True})

        # Paid per the provider, but our webhook hasn't recorded it yet —
        # do not fabricate an Order here (that's the webhook's job alone);
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
class GatewayWebhookView(APIView):
    """Base for all 8 gateway webhook views (POST /webhooks/<gateway>/) —
    the ONLY place an Order is created for a real (non-fake) provider.
    Never rate-limited (a dropped legitimate webhook silently loses an
    order) and never CSRF-checked (the gateway can't present a token) —
    authenticity comes entirely from each provider's own signature
    verification. authentication_classes=[]: see CheckoutView's docstring —
    SessionAuthentication's own CSRF check is independent of csrf_exempt,
    and there's no legitimate requester to authenticate here anyway (the
    gateway's server, not a browser session).

    Subclasses set `gateway`. The webhook payload identifies which SELLER
    it belongs to only implicitly (via the session/reference id an earlier
    checkout already recorded nowhere obvious) — real gateways carry the
    merchant/account identity in the credentials used to verify the
    signature, not in the payload, so every owner who has this gateway
    enabled is tried in turn until one successfully verifies the signature.
    This is the same tradeoff every multi-tenant webhook integration faces
    without a per-owner webhook URL/path; scoped here as "try each
    candidate owner's credentials", not left unverified.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    gateway: str = ""

    def post(self, request):
        configs = PaymentGatewayConfig.objects.filter(gateway=self.gateway, is_enabled=True)
        headers = request.META
        query_params = request.GET
        payload = request.body

        event = None
        matched_config = None
        for config in configs:
            provider = build_payment_provider(self.gateway, config.get_credentials())
            if type(provider).__name__.startswith("Fake"):
                continue  # a real webhook can never be authenticated by a fake provider
            try:
                event = provider.parse_webhook_event(
                    payload=payload, headers=headers, query_params=query_params
                )
                matched_config = config
                break
            except PaymentProviderError:
                continue

        if event is None or matched_config is None:
            logger.warning(
                "rejected %s webhook: no matching enabled seller verified it", self.gateway
            )
            return Response(status=400)

        session_id, product_id = self._extract_session_and_product(event)
        if not session_id:
            return Response(status=200)  # an event type we don't act on

        provider = build_payment_provider(self.gateway, matched_config.get_credentials())
        try:
            _record_order_for_session(provider, self.gateway, session_id, product_id)
        except PaymentProviderError:
            logger.exception(
                "could not retrieve %s session %s for webhook processing", self.gateway, session_id
            )
            return Response(status=502)

        return Response(status=200)

    def _extract_session_and_product(self, event):
        """Gateway-specific: where the session/reference id and our own
        client_reference_id live in that gateway's event shape. Returns
        (session_id, product_id) — session_id None means "ignore this
        event type", matching Stripe's own
        checkout.session.completed-only filter."""
        raise NotImplementedError


class StripeWebhookView(GatewayWebhookView):
    gateway = "stripe"

    def _extract_session_and_product(self, event):
        # event is always a plain dict here — both FakeStripeProvider
        # (json.loads) and StripePaymentProvider (event.to_dict()) return one.
        if event.get("type") != "checkout.session.completed":
            return None, None
        session_obj = event.get("data", {}).get("object", {})
        return session_obj.get("id"), session_obj.get("client_reference_id")


class MercadoPagoWebhookView(GatewayWebhookView):
    gateway = "mercadopago"

    def _extract_session_and_product(self, event):
        if event.get("type") != "payment":
            return None, None
        return str(event.get("data", {}).get("id", "")), None


class PayPalWebhookView(GatewayWebhookView):
    gateway = "paypal"

    def _extract_session_and_product(self, event):
        resource = event.get("resource", {}) if isinstance(event, dict) else {}
        order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        product_id = None
        for unit in resource.get("purchase_units", []) or []:
            product_id = unit.get("reference_id")
            if product_id:
                break
        return order_id or resource.get("id"), product_id


class BraintreeWebhookView(GatewayWebhookView):
    gateway = "braintree"

    def _extract_session_and_product(self, event):
        return event.get("transaction_id"), None


class WompiWebhookView(GatewayWebhookView):
    gateway = "wompi"

    def _extract_session_and_product(self, event):
        transaction = event.get("data", {}).get("transaction", {})
        return transaction.get("reference"), None


class PayUWebhookView(GatewayWebhookView):
    gateway = "payu"

    def _extract_session_and_product(self, event):
        return event.get("reference_sale"), None


class EpaycoWebhookView(GatewayWebhookView):
    gateway = "epayco"

    def _extract_session_and_product(self, event):
        return event.get("x_ref_payco"), None


class BoldWebhookView(GatewayWebhookView):
    gateway = "bold"

    def _extract_session_and_product(self, event):
        # BoldPaymentProvider.parse_webhook_event always raises (unverified,
        # see payments.py) — this is never actually reached until that's
        # implemented for real, kept only so the URL/view exists.
        return None, None


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


@require_http_methods(["GET"])
def payu_redirect_view(request):
    """GET /pagar/payu/redirect/ — PayU's WebCheckout is a client-side POST
    to their own hosted page (no create-session API call exists), so this
    renders the tiny auto-submitting form CheckoutView's PayU session URL
    points at. Every field PayUPaymentProvider already computed is passed
    through as query params — this view only turns them into hidden
    <input>s and auto-submits; it never re-derives or trusts anything."""
    return render(request, "storefront/payu_redirect.html", {"fields": request.GET.dict()})
