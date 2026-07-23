"""Swappable payment providers — mirrors apps/ai_assistant/providers.py's
AIProvider/FakeAIProvider pattern: a small ABC, one fake implementation per
gateway (tests and local dev use these by default, no network), and one
real implementation per gateway selected only once that gateway's own
credentials are configured (see PaymentGatewayConfig / build_payment_provider).

Buyer picks the gateway at checkout — all configured gateways can be live
simultaneously (PAYMENTS.md). Every gateway that has no real credentials
configured falls back to its own Fake* variant so all buttons "work" in
dev/demo without any real keys.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import parse_qs

GATEWAY_CHOICES = [
    "stripe",
    "mercadopago",
    "paypal",
    "braintree",
    "wompi",
    "payu",
    "epayco",
    "bold",
]


class PaymentProviderError(Exception):
    """Raised when the payment provider itself fails (network, API error,
    or webhook signature verification failure)."""


@dataclass
class CheckoutSession:
    id: str
    url: str


@dataclass
class SessionStatus:
    id: str
    payment_status: str  # "paid" | "unpaid" | "no_payment_required"
    amount_total: int
    currency: str
    customer_email: str


class PaymentProvider(ABC):
    @abstractmethod
    def create_checkout_session(
        self,
        *,
        product_name: str,
        amount_cents: int,
        currency: str,
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
    ) -> CheckoutSession: ...

    @abstractmethod
    def retrieve_session(self, session_id: str) -> SessionStatus: ...

    @abstractmethod
    def parse_webhook_event(self, *, payload: bytes, headers: dict, query_params: dict) -> dict:
        """Verify and parse an inbound webhook payload. Raise
        PaymentProviderError if signature verification fails — the caller
        must reject the request (400), never process an unverified event.

        `headers` is a Django-style META dict (HTTP_X_FOO for header X-Foo);
        `query_params` is the request's GET dict — some gateways (Mercado
        Pago) put verification data in the query string, not just headers.
        """
        ...


# ---------------------------------------------------------------------------
# Stripe (unchanged behavior, now takes no constructor-time settings object —
# credentials are always passed to the constructor explicitly, never read
# from Django settings inside the provider itself, so
# PaymentGatewayConfig-sourced credentials and env-var-sourced ones work the
# same way).
# ---------------------------------------------------------------------------


class FakePaymentProvider(PaymentProvider):
    """Base fake: deterministic, no-network, class-level `_sessions` dict so
    a later retrieve_session (e.g. the success-page race-condition fallback)
    sees what an earlier create_checkout_session produced. Subclassed per
    gateway ONLY so each gateway's fake sessions live in separate dicts
    (never share one namespace — a webhook/checkout test for one gateway
    must never accidentally see another's fake session)."""

    _sessions: dict[str, dict] = {}
    _id_prefix = "cs_test_fake"

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        session_id = f"{self._id_prefix}_{uuid.uuid4().hex}"
        self._sessions[session_id] = {
            "amount_total": amount_cents,
            "currency": currency,
            "payment_status": "paid",  # the fake provider simulates an instantly-successful payment
            "customer_email": "buyer@example.com",
            "client_reference_id": client_reference_id,
        }
        # Mirrors Stripe's own success_url contract: the caller embeds the
        # literal "{CHECKOUT_SESSION_ID}" placeholder, the provider
        # substitutes it — never append a second query param instead.
        resolved_url = success_url.replace("{CHECKOUT_SESSION_ID}", session_id)
        return CheckoutSession(id=session_id, url=resolved_url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        data = self._sessions.get(session_id)
        if not data:
            raise PaymentProviderError(f"unknown fake session: {session_id}")
        return SessionStatus(
            id=session_id,
            payment_status=data["payment_status"],
            amount_total=data["amount_total"],
            currency=data["currency"],
            customer_email=data["customer_email"],
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        # No real signature to check — tests construct the payload directly.
        # Trusted only because a fake provider is never selected once real
        # credentials are configured for this gateway.
        return json.loads(payload)


class FakeStripeProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "cs_test_fake_stripe"


class StripePaymentProvider(PaymentProvider):
    def __init__(self, *, secret_key: str, webhook_secret: str = ""):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret

    def _client(self):
        import stripe

        stripe.api_key = self.secret_key
        return stripe

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        stripe = self._client()
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                client_reference_id=client_reference_id,
                line_items=[
                    {
                        "price_data": {
                            "currency": currency,
                            "product_data": {"name": product_name},
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except stripe.error.StripeError as exc:
            raise PaymentProviderError(str(exc)) from exc
        return CheckoutSession(id=session.id, url=session.url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        stripe = self._client()
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as exc:
            raise PaymentProviderError(str(exc)) from exc
        return SessionStatus(
            id=session.id,
            payment_status=session.payment_status,
            amount_total=session.amount_total,
            currency=session.currency,
            customer_email=(session.customer_details or {}).get("email", "")
            if isinstance(session.customer_details, dict)
            else getattr(session.customer_details, "email", "") or "",
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        stripe = self._client()
        sig_header = headers.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise PaymentProviderError(str(exc)) from exc
        # construct_event returns a StripeObject (no .get(), no isinstance(
        # dict) match) — normalize to a plain dict so callers never need to
        # special-case "real Stripe event" vs "fake provider's json.loads
        # dict" differently. A real bug the moment this was ever exercised
        # against a real signed event instead of only FakePaymentProvider's
        # already-plain-dict output.
        return event.to_dict()


# ---------------------------------------------------------------------------
# Mercado Pago — Checkout Pro preference + payment lookup. Webhook signature
# per MP's own docs (verified this session): "x-signature: ts=<ts>,v1=<hmac>"
# plus "x-request-id" header and the resource id from the query string
# (?data.id=...). The exact manifest string below
# ("id:{id};request-id:{req_id};ts:{ts};") is MP's documented format for the
# "payment" topic — PAYMENTS.md flags this as needing re-confirmation against
# live docs/SDK before trusting in production; this is the best-documented
# version found during that research pass.
# ---------------------------------------------------------------------------


class FakeMercadoPagoProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "mp_test_fake"


class MercadoPagoPaymentProvider(PaymentProvider):
    def __init__(self, *, access_token: str, webhook_secret: str = ""):
        self.access_token = access_token
        self.webhook_secret = webhook_secret

    def _sdk(self):
        import mercadopago

        return mercadopago.SDK(self.access_token)

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        sdk = self._sdk()
        preference_data = {
            "items": [
                {
                    "title": product_name,
                    "quantity": 1,
                    "unit_price": amount_cents / 100,
                    "currency_id": currency.upper(),
                }
            ],
            "external_reference": client_reference_id,
            "back_urls": {
                "success": success_url.replace("{CHECKOUT_SESSION_ID}", ""),
                "failure": cancel_url,
                "pending": cancel_url,
            },
        }
        try:
            response = sdk.preference().create(preference_data)
        except Exception as exc:  # SDK raises plain exceptions, not a typed hierarchy
            raise PaymentProviderError(str(exc)) from exc
        preference = response.get("response", {})
        preference_id = preference.get("id")
        if not preference_id:
            raise PaymentProviderError(f"unexpected Mercado Pago response: {response}")
        # Sandbox uses sandbox_init_point; fall back to init_point for a
        # fully-approved production integration.
        url = preference.get("sandbox_init_point") or preference.get("init_point")
        return CheckoutSession(id=preference_id, url=url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        sdk = self._sdk()
        try:
            response = sdk.payment().get(session_id)
        except Exception as exc:
            raise PaymentProviderError(str(exc)) from exc
        payment = response.get("response", {})
        if not payment or "status" not in payment:
            raise PaymentProviderError(f"unknown Mercado Pago payment: {session_id}")
        return SessionStatus(
            id=str(payment.get("id")),
            payment_status="paid" if payment.get("status") == "approved" else "unpaid",
            amount_total=int(round((payment.get("transaction_amount") or 0) * 100)),
            currency=str(payment.get("currency_id", "")).lower(),
            customer_email=(payment.get("payer") or {}).get("email", ""),
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        signature = headers.get("HTTP_X_SIGNATURE", "")
        request_id = headers.get("HTTP_X_REQUEST_ID", "")
        data_id = query_params.get("data.id") or query_params.get("id", "")
        parts = dict(p.split("=", 1) for p in signature.split(",") if "=" in p)
        ts = parts.get("ts", "")
        provided_hash = parts.get("v1", "")
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        expected_hash = hmac.new(
            self.webhook_secret.encode(), manifest.encode(), hashlib.sha256
        ).hexdigest()
        if not provided_hash or not hmac.compare_digest(provided_hash, expected_hash):
            raise PaymentProviderError("invalid Mercado Pago webhook signature")
        return json.loads(payload)


# ---------------------------------------------------------------------------
# PayPal — Orders API v2. The one gateway whose webhook verification is a
# server-to-server API call (verify-webhook-signature), not a local HMAC —
# parse_webhook_event makes an outbound HTTPS request; FakePayPalProvider
# never does (matches this project's "tests never hit a real API" rule).
# ---------------------------------------------------------------------------


class FakePayPalProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "paypal_test_fake"


class PayPalPaymentProvider(PaymentProvider):
    def __init__(
        self, *, client_id: str, client_secret: str, webhook_id: str = "", env: str = "sandbox"
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.webhook_id = webhook_id
        self.base_url = (
            "https://api-m.sandbox.paypal.com" if env != "live" else "https://api-m.paypal.com"
        )

    def _access_token(self):
        import requests

        try:
            resp = requests.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PaymentProviderError(str(exc)) from exc
        return resp.json()["access_token"]

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        import requests

        token = self._access_token()
        body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": client_reference_id,
                    "description": product_name,
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": f"{amount_cents / 100:.2f}",
                    },
                }
            ],
            "application_context": {
                "return_url": success_url.replace("{CHECKOUT_SESSION_ID}", ""),
                "cancel_url": cancel_url,
            },
        }
        try:
            resp = requests.post(
                f"{self.base_url}/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PaymentProviderError(str(exc)) from exc
        data = resp.json()
        approve_link = next(
            (link["href"] for link in data.get("links", []) if link.get("rel") == "approve"), None
        )
        if not approve_link:
            raise PaymentProviderError(f"no approve link in PayPal response: {data}")
        return CheckoutSession(id=data["id"], url=approve_link)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        import requests

        token = self._access_token()
        try:
            resp = requests.get(
                f"{self.base_url}/v2/checkout/orders/{session_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PaymentProviderError(str(exc)) from exc
        data = resp.json()
        unit = (data.get("purchase_units") or [{}])[0]
        amount = unit.get("amount", {})
        payer_email = (data.get("payer") or {}).get("email_address", "")
        status = data.get("status", "")
        return SessionStatus(
            id=data["id"],
            payment_status="paid" if status in ("COMPLETED", "APPROVED") else "unpaid",
            amount_total=int(round(float(amount.get("value", 0)) * 100)),
            currency=str(amount.get("currency_code", "")).lower(),
            customer_email=payer_email,
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        import requests

        token = self._access_token()
        verification_body = {
            "transmission_id": headers.get("HTTP_PAYPAL_TRANSMISSION_ID", ""),
            "transmission_time": headers.get("HTTP_PAYPAL_TRANSMISSION_TIME", ""),
            "cert_url": headers.get("HTTP_PAYPAL_CERT_URL", ""),
            "auth_algo": headers.get("HTTP_PAYPAL_AUTH_ALGO", ""),
            "transmission_sig": headers.get("HTTP_PAYPAL_TRANSMISSION_SIG", ""),
            "webhook_id": self.webhook_id,
            "webhook_event": json.loads(payload),
        }
        try:
            resp = requests.post(
                f"{self.base_url}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=verification_body,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PaymentProviderError(str(exc)) from exc
        if resp.json().get("verification_status") != "SUCCESS":
            raise PaymentProviderError("invalid PayPal webhook signature")
        return verification_body["webhook_event"]


# ---------------------------------------------------------------------------
# Braintree — the SDK verifies its own webhooks (gateway.webhook_notification
# .parse), so parse_webhook_event is a thin wrapper, not a hand-rolled HMAC.
# Notification arrives as form-encoded POST body fields (bt_signature,
# bt_payload), NOT as JSON — unlike every other gateway here.
# ---------------------------------------------------------------------------


class FakeBraintreeProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "bt_test_fake"


class BraintreePaymentProvider(PaymentProvider):
    def __init__(
        self, *, merchant_id: str, public_key: str, private_key: str, env: str = "sandbox"
    ):
        self.merchant_id = merchant_id
        self.public_key = public_key
        self.private_key = private_key
        self.env = env

    def _gateway(self):
        import braintree

        environment = (
            braintree.Environment.Sandbox
            if self.env != "live"
            else braintree.Environment.Production
        )
        return braintree.BraintreeGateway(
            braintree.Configuration(
                environment=environment,
                merchant_id=self.merchant_id,
                public_key=self.public_key,
                private_key=self.private_key,
            )
        )

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        # Braintree has no hosted "redirect to their page" checkout API akin
        # to the others (its native flow is Drop-in/hosted fields embedded
        # in OUR page) — PAYMENTS.md scoped this to the redirect-style
        # contract for architectural consistency with the other 7 gateways.
        # A minimal, real redirect option is a client_token-backed page this
        # app serves itself; that page's URL is the "session url" here.
        gateway = self._gateway()
        try:
            client_token = gateway.client_token.generate()
        except Exception as exc:
            raise PaymentProviderError(str(exc)) from exc
        session_id = f"bt_{uuid.uuid4().hex}"
        FakeBraintreeProvider._sessions[session_id] = {
            "amount_total": amount_cents,
            "currency": currency,
            "payment_status": "unpaid",
            "customer_email": "",
            "client_reference_id": client_reference_id,
            "client_token": client_token,
        }
        url = success_url.replace("{CHECKOUT_SESSION_ID}", session_id).replace(
            "gracias", f"pagar/braintree/{session_id}"
        )
        return CheckoutSession(id=session_id, url=url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        gateway = self._gateway()
        try:
            transaction = gateway.transaction.find(session_id)
        except Exception as exc:
            raise PaymentProviderError(str(exc)) from exc
        return SessionStatus(
            id=transaction.id,
            payment_status="paid" if str(transaction.status) == "settled" else "unpaid",
            amount_total=int(round(float(transaction.amount) * 100)),
            currency=str(transaction.currency_iso_code).lower(),
            customer_email=(transaction.customer or {}).get("email", "") or "",
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        gateway = self._gateway()
        fields = parse_qs(payload.decode())
        bt_signature = fields.get("bt_signature", [""])[0]
        bt_payload = fields.get("bt_payload", [""])[0]
        try:
            notification = gateway.webhook_notification.parse(bt_signature, bt_payload)
        except Exception as exc:
            raise PaymentProviderError(str(exc)) from exc
        transaction = getattr(notification, "transaction", None)
        return {
            "kind": notification.kind,
            "transaction_id": getattr(transaction, "id", None),
            "status": str(getattr(transaction, "status", "")),
        }


# ---------------------------------------------------------------------------
# Wompi (Colombia) — hosted Web Checkout redirect with an integrity
# signature on the way in, and a separate event checksum on the webhook.
# No official Python SDK; talks to Wompi's REST API directly via requests.
# ---------------------------------------------------------------------------


class FakeWompiProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "wompi_test_fake"


class WompiPaymentProvider(PaymentProvider):
    SANDBOX_BASE_URL = "https://sandbox.wompi.co/v1"
    CHECKOUT_BASE_URL = "https://checkout.wompi.co/p/"

    def __init__(
        self, *, public_key: str, private_key: str, integrity_secret: str, events_secret: str = ""
    ):
        self.public_key = public_key
        self.private_key = private_key
        self.integrity_secret = integrity_secret
        self.events_secret = events_secret

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        reference = f"wompi_{uuid.uuid4().hex}"
        signature_source = f"{reference}{amount_cents}{currency.upper()}{self.integrity_secret}"
        integrity_signature = hashlib.sha256(signature_source.encode()).hexdigest()
        redirect_url = success_url.replace("{CHECKOUT_SESSION_ID}", reference)
        url = (
            f"{self.CHECKOUT_BASE_URL}?public-key={self.public_key}&currency={currency.upper()}"
            f"&amount-in-cents={amount_cents}&reference={reference}"
            f"&signature:integrity={integrity_signature}&redirect-url={redirect_url}"
        )
        return CheckoutSession(id=reference, url=url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        import requests

        try:
            resp = requests.get(
                f"{self.SANDBOX_BASE_URL}/transactions?reference={session_id}",
                headers={"Authorization": f"Bearer {self.private_key}"},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise PaymentProviderError(str(exc)) from exc
        results = resp.json().get("data", [])
        if not results:
            raise PaymentProviderError(f"unknown Wompi reference: {session_id}")
        transaction = results[0]
        return SessionStatus(
            id=transaction.get("reference", session_id),
            payment_status="paid" if transaction.get("status") == "APPROVED" else "unpaid",
            amount_total=transaction.get("amount_in_cents", 0),
            currency=str(transaction.get("currency", "")).lower(),
            customer_email=(transaction.get("customer_email") or ""),
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        event = json.loads(payload)
        signature = event.get("signature", {})
        provided_checksum = signature.get("checksum", "")
        properties = signature.get("properties", [])
        data = event.get("data", {})

        def _lookup(path: str):
            node = data
            for part in path.split("."):
                node = node.get(part, {}) if isinstance(node, dict) else None
            return node

        concatenated = "".join(str(_lookup(prop) or "") for prop in properties)
        concatenated += str(event.get("timestamp", ""))
        concatenated += self.events_secret
        expected_checksum = hashlib.sha256(concatenated.encode()).hexdigest()
        if not provided_checksum or not hmac.compare_digest(
            provided_checksum.lower(), expected_checksum.lower()
        ):
            raise PaymentProviderError("invalid Wompi webhook checksum")
        return event


# ---------------------------------------------------------------------------
# PayU LatAm — WebCheckout: our own server renders a hidden auto-submit form
# POSTing to PayU's hosted page (there is no "create session" API call), so
# CheckoutSession.url here points at a small view of our own, not a PayU URL.
# ---------------------------------------------------------------------------


class FakePayUProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "payu_test_fake"


class PayUPaymentProvider(PaymentProvider):
    SANDBOX_CHECKOUT_URL = "https://sandbox.checkout.payulatam.com/ppp-web-gateway-payu/"

    def __init__(self, *, merchant_id: str, account_id: str, api_key: str, api_login: str = ""):
        self.merchant_id = merchant_id
        self.account_id = account_id
        self.api_key = api_key
        self.api_login = api_login

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        reference_code = f"payu_{uuid.uuid4().hex}"
        # PayU signs a fixed-decimal amount string (e.g. "10.00") — verify
        # this formatting against live docs before trusting it in production
        # (PAYMENTS.md 2.6 flags this as PayU's best-known integration gotcha).
        amount_str = f"{amount_cents / 100:.2f}"
        signature_source = (
            f"{self.api_key}~{self.merchant_id}~{reference_code}~{amount_str}~{currency.upper()}"
        )
        signature = hashlib.md5(signature_source.encode()).hexdigest()  # noqa: S324 — PayU's own documented scheme, not our choice
        # Our own view (Section 4 of PAYMENTS.md) renders the actual
        # auto-submit <form> from these fields — CheckoutSession.url points
        # there, not directly at PayU, since WebCheckout is POST-redirect.
        confirmation_url = success_url.replace("{CHECKOUT_SESSION_ID}", reference_code)
        params = (
            f"merchantId={self.merchant_id}&accountId={self.account_id}"
            f"&referenceCode={reference_code}&amount={amount_str}&currency={currency.upper()}"
            f"&signature={signature}&description={product_name}"
            f"&responseUrl={cancel_url}&confirmationUrl={confirmation_url}"
        )
        url = f"/pagar/payu/redirect/?{params}"
        return CheckoutSession(id=reference_code, url=url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        # PayU has no simple "retrieve by reference" REST call comparable to
        # the others without their full Reports API — the success-page
        # race-condition fallback (see views.py) simply shows "pending"
        # until the confirmation webhook lands for this gateway.
        raise PaymentProviderError("PayU session lookup requires the confirmation webhook")

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        fields = {k: v[0] for k, v in parse_qs(payload.decode()).items()}
        reference_sale = fields.get("reference_sale", "")
        value = fields.get("value", "")
        currency = fields.get("currency", "")
        state_pol = fields.get("state_pol", "")
        provided_sign = fields.get("sign", "")
        signature_source = (
            f"{self.api_key}~{self.merchant_id}~{reference_sale}~{value}~{currency}~{state_pol}"
        )
        expected_sign = hashlib.md5(signature_source.encode()).hexdigest()  # noqa: S324
        if not provided_sign or not hmac.compare_digest(provided_sign, expected_sign):
            raise PaymentProviderError("invalid PayU confirmation signature")
        return fields


# ---------------------------------------------------------------------------
# ePayco (Colombia) — hosted Checkout widget/redirect; confirmation webhook
# signature per ePayco's well-known public pattern. This session's own fetch
# of epayco's docs failed (connection refused) — PAYMENTS.md 2.7 flags this
# formula as unconfirmed-live, a strong guess rather than a re-verified spec.
# ---------------------------------------------------------------------------


class FakeEpaycoProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "epayco_test_fake"


class EpaycoPaymentProvider(PaymentProvider):
    def __init__(self, *, public_key: str, p_key: str, p_cust_id_cliente: str):
        self.public_key = public_key
        self.p_key = p_key
        self.p_cust_id_cliente = p_cust_id_cliente

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        reference = f"epayco_{uuid.uuid4().hex}"
        confirmation_url = success_url.replace("{CHECKOUT_SESSION_ID}", reference)
        params = (
            f"public-key={self.public_key}&name={product_name}"
            f"&amount={amount_cents / 100:.2f}&currency={currency.lower()}"
            f"&invoice={reference}"
            f"&response={cancel_url}&confirmation={confirmation_url}"
        )
        url = f"https://checkout.epayco.co/checkout.js?{params}"
        return CheckoutSession(id=reference, url=url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        raise PaymentProviderError("ePayco session lookup requires the confirmation webhook")

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        fields = {k: v[0] for k, v in parse_qs(payload.decode()).items()}
        ref_payco = fields.get("x_ref_payco", "")
        transaction_id = fields.get("x_transaction_id", "")
        amount = fields.get("x_amount", "")
        currency_code = fields.get("x_currency_code", "")
        provided_signature = fields.get("x_signature", "")
        signature_source = (
            f"{self.p_cust_id_cliente}^{self.p_key}^{ref_payco}^{transaction_id}"
            f"^{amount}^{currency_code}"
        )
        expected_signature = hashlib.sha256(signature_source.encode()).hexdigest()
        if not provided_signature or not hmac.compare_digest(
            provided_signature, expected_signature
        ):
            raise PaymentProviderError("invalid ePayco confirmation signature")
        return fields


# ---------------------------------------------------------------------------
# Bold (Colombia) — LOWEST CONFIDENCE integration in this file. Bold's docs
# site is JS-rendered and did not yield usable field/signature specs during
# PAYMENTS.md's research pass (only navigation chrome came back). This is a
# best-effort placeholder mirroring Wompi's integrity-signature shape (same
# country/market, structurally similar vendor pattern) — treat as
# NOT VERIFIED. Re-fetch Bold's actual "Esquema de datos"/"Webhook" docs
# before relying on this in anything beyond the fake-provider dev path.
# ---------------------------------------------------------------------------


class FakeBoldProvider(FakePaymentProvider):
    _sessions: dict[str, dict] = {}
    _id_prefix = "bold_test_fake"


class BoldPaymentProvider(PaymentProvider):
    def __init__(self, *, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        order_id = f"bold_{uuid.uuid4().hex}"
        signature_source = f"{order_id}{amount_cents}{currency.upper()}{self.secret_key}"
        integrity_signature = hashlib.sha256(signature_source.encode()).hexdigest()
        redirect_url = success_url.replace("{CHECKOUT_SESSION_ID}", order_id)
        url = (
            f"https://checkout.bold.co/?api-key={self.api_key}&order-id={order_id}"
            f"&amount={amount_cents}&currency={currency.upper()}&description={product_name}"
            f"&integrity-signature={integrity_signature}&redirect-url={redirect_url}"
        )
        return CheckoutSession(id=order_id, url=url)

    def retrieve_session(self, session_id: str) -> SessionStatus:
        raise PaymentProviderError(
            "Bold session lookup requires the webhook — not yet verified, see PAYMENTS.md 2.8"
        )

    def parse_webhook_event(self, *, payload, headers, query_params) -> dict:
        raise PaymentProviderError(
            "BoldPaymentProvider.parse_webhook_event is unverified — do not trust in "
            "production until Bold's real webhook docs are confirmed (PAYMENTS.md 2.8)"
        )


# ---------------------------------------------------------------------------
# Registry — one place mapping a gateway string to its real/fake pair. Real
# credentials are looked up from PaymentGatewayConfig (DB, encrypted) with a
# settings/.env fallback for Stripe (unchanged, pre-existing behavior).
# ---------------------------------------------------------------------------


def _stripe_provider(creds: dict) -> PaymentProvider:
    return StripePaymentProvider(
        secret_key=creds["secret_key"], webhook_secret=creds.get("webhook_secret", "")
    )


def _mercadopago_provider(creds: dict) -> PaymentProvider:
    return MercadoPagoPaymentProvider(
        access_token=creds["access_token"], webhook_secret=creds.get("webhook_secret", "")
    )


def _paypal_provider(creds: dict) -> PaymentProvider:
    return PayPalPaymentProvider(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        webhook_id=creds.get("webhook_id", ""),
        env=creds.get("env", "sandbox"),
    )


def _braintree_provider(creds: dict) -> PaymentProvider:
    return BraintreePaymentProvider(
        merchant_id=creds["merchant_id"],
        public_key=creds["public_key"],
        private_key=creds["private_key"],
        env=creds.get("env", "sandbox"),
    )


def _wompi_provider(creds: dict) -> PaymentProvider:
    return WompiPaymentProvider(
        public_key=creds["public_key"],
        private_key=creds["private_key"],
        integrity_secret=creds["integrity_secret"],
        events_secret=creds.get("events_secret", ""),
    )


def _payu_provider(creds: dict) -> PaymentProvider:
    return PayUPaymentProvider(
        merchant_id=creds["merchant_id"],
        account_id=creds["account_id"],
        api_key=creds["api_key"],
        api_login=creds.get("api_login", ""),
    )


def _epayco_provider(creds: dict) -> PaymentProvider:
    return EpaycoPaymentProvider(
        public_key=creds["public_key"],
        p_key=creds["p_key"],
        p_cust_id_cliente=creds["p_cust_id_cliente"],
    )


def _bold_provider(creds: dict) -> PaymentProvider:
    return BoldPaymentProvider(api_key=creds["api_key"], secret_key=creds["secret_key"])


# gateway -> (required credential field names, real-provider factory, fake class)
GATEWAY_REGISTRY = {
    "stripe": (["secret_key"], _stripe_provider, FakeStripeProvider),
    "mercadopago": (["access_token"], _mercadopago_provider, FakeMercadoPagoProvider),
    "paypal": (["client_id", "client_secret"], _paypal_provider, FakePayPalProvider),
    "braintree": (
        ["merchant_id", "public_key", "private_key"],
        _braintree_provider,
        FakeBraintreeProvider,
    ),
    "wompi": (
        ["public_key", "private_key", "integrity_secret"],
        _wompi_provider,
        FakeWompiProvider,
    ),
    "payu": (["merchant_id", "account_id", "api_key"], _payu_provider, FakePayUProvider),
    "epayco": (["public_key", "p_key", "p_cust_id_cliente"], _epayco_provider, FakeEpaycoProvider),
    "bold": (["api_key", "secret_key"], _bold_provider, FakeBoldProvider),
}


def build_payment_provider(gateway: str, credentials: dict | None) -> PaymentProvider:
    """credentials is None (no PaymentGatewayConfig row, or the row is
    disabled/incomplete) -> the gateway's Fake variant. Never falls back to
    a real provider with partial credentials — an incomplete config is
    exactly as "not configured" as no config at all."""
    if gateway not in GATEWAY_REGISTRY:
        raise PaymentProviderError(f"unknown payment gateway: {gateway}")
    required_fields, real_factory, fake_cls = GATEWAY_REGISTRY[gateway]
    if credentials and all(credentials.get(f) for f in required_fields):
        return real_factory(credentials)
    return fake_cls()
