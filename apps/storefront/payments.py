"""Swappable payment provider — mirrors apps/ai_assistant/providers.py's
AIProvider/FakeAIProvider pattern exactly: a small ABC, a fake
implementation tests and local dev use by default, and a real one
selected only once a secret key is configured (PAYMENT_PROVIDER setting).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


class PaymentProviderError(Exception):
    """Raised when the payment provider itself fails (network, API error)."""


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
    def parse_webhook_event(self, *, payload: bytes, sig_header: str, webhook_secret: str) -> dict:
        """Verify and parse an inbound webhook payload. Raise
        PaymentProviderError if signature verification fails — the caller
        must reject the request (400), never process an unverified event."""
        ...


class FakePaymentProvider(PaymentProvider):
    """Deterministic, no-network provider for tests and no-key development.
    Keeps created sessions in a class-level dict so a later
    retrieve_session (e.g. the success-page race-condition fallback,
    FEATURE.md 1.6b) sees what an earlier create_checkout_session produced
    — a fresh instance is built per request, same as FakeAIProvider, but
    the "backend" needs to persist across those instances within a test.
    """

    _sessions: dict[str, dict] = {}

    def create_checkout_session(
        self, *, product_name, amount_cents, currency, success_url, cancel_url, client_reference_id
    ) -> CheckoutSession:
        session_id = f"cs_test_fake_{uuid.uuid4().hex}"
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

    def parse_webhook_event(self, *, payload, sig_header, webhook_secret) -> dict:
        # No real signature to check — tests construct the payload
        # directly. Trusted only because PAYMENT_PROVIDER=fake is never
        # selected once a real STRIPE_SECRET_KEY is configured.
        import json

        return json.loads(payload)


class StripePaymentProvider(PaymentProvider):
    def __init__(self, *, secret_key: str):
        self.secret_key = secret_key

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

    def parse_webhook_event(self, *, payload, sig_header, webhook_secret) -> dict:
        stripe = self._client()
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise PaymentProviderError(str(exc)) from exc
        return event


def build_payment_provider(settings) -> PaymentProvider:
    provider = getattr(settings, "PAYMENT_PROVIDER", "fake")
    if provider == "stripe" and settings.STRIPE_SECRET_KEY:
        return StripePaymentProvider(secret_key=settings.STRIPE_SECRET_KEY)
    return FakePaymentProvider()
