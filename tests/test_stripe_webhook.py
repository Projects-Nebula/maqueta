import hashlib
import hmac
import json
import time

import pytest

from apps.storefront.models import Order, PaymentGatewayConfig, Product
from apps.storefront.payments import (
    FakeStripeProvider,
    PaymentProviderError,
    SessionStatus,
    StripePaymentProvider,
)

pytestmark = pytest.mark.django_db

WEBHOOK_URL = "/webhooks/stripe/"
WEBHOOK_SECRET = "whsec_test_fake_secret"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _completed_event(session_id, product_id):
    return json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "client_reference_id": str(product_id)}},
        }
    ).encode()


@pytest.fixture(autouse=True)
def _clear_fake_sessions():
    FakeStripeProvider._sessions.clear()
    yield
    FakeStripeProvider._sessions.clear()


def _enable_real_stripe(owner, secret_key="sk_test_fake", webhook_secret=WEBHOOK_SECRET):
    config = PaymentGatewayConfig.objects.create(owner=owner, gateway="stripe", is_enabled=True)
    config.set_credentials({"secret_key": secret_key, "webhook_secret": webhook_secret})
    config.save()
    return config


def _mock_paid_session(monkeypatch, *, amount_cents=1999, currency="usd"):
    # retrieve_session would normally hit the real Stripe API — mocked
    # since these tests exercise the webhook dispatch/signature/owner-
    # matching logic, not Stripe's own API client (already covered by
    # StripePaymentProvider's real HTTP calls elsewhere / manually).
    monkeypatch.setattr(
        StripePaymentProvider,
        "retrieve_session",
        lambda self, sid: SessionStatus(
            id=sid,
            payment_status="paid",
            amount_total=amount_cents,
            currency=currency,
            customer_email="buyer@example.com",
        ),
    )


def test_webhook_creates_order_on_completed_session(anon_api, user, monkeypatch):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_real_stripe(user)
    _mock_paid_session(monkeypatch)

    session_id = "cs_test_real_123"
    body = _completed_event(session_id, product.id)
    response = anon_api.post(
        WEBHOOK_URL, data=body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_sign(body)
    )
    assert response.status_code == 200
    order = Order.objects.get(gateway="stripe", gateway_session_id=session_id)
    assert order.status == Order.Status.PAID
    assert order.amount_cents == 1999
    assert order.product_id == product.id


def test_webhook_is_idempotent_on_replay(anon_api, user, monkeypatch):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_real_stripe(user)
    _mock_paid_session(monkeypatch)

    body = _completed_event("cs_test_replay", product.id)
    anon_api.post(
        WEBHOOK_URL, data=body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_sign(body)
    )
    anon_api.post(
        WEBHOOK_URL, data=body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_sign(body)
    )

    assert Order.objects.filter(gateway="stripe", gateway_session_id="cs_test_replay").count() == 1


def test_webhook_sets_download_token_for_digital_product(anon_api, user, monkeypatch):
    from django.core.files.base import ContentFile

    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    product.digital_file.save("book.pdf", ContentFile(b"%PDF-1.4\nfake"), save=True)
    _enable_real_stripe(user)
    _mock_paid_session(monkeypatch)

    body = _completed_event("cs_test_digital", product.id)
    anon_api.post(
        WEBHOOK_URL, data=body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_sign(body)
    )

    order = Order.objects.get(gateway="stripe", gateway_session_id="cs_test_digital")
    assert order.download_token


def test_webhook_ignores_unrelated_event_types(anon_api, user):
    _enable_real_stripe(user)
    body = json.dumps(
        {
            "id": "evt_x",
            "object": "event",
            "type": "payment_intent.created",
            "data": {"object": {"id": "x"}},
        }
    ).encode()

    response = anon_api.post(
        WEBHOOK_URL, data=body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_sign(body)
    )
    assert response.status_code == 200
    assert Order.objects.count() == 0


def test_webhook_rejects_bad_signature(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_real_stripe(user)

    body = _completed_event("cs_test_bad_sig", product.id)
    response = anon_api.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=123,v1=not-a-real-signature",
    )
    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_webhook_rejects_when_no_seller_ever_enabled_stripe(anon_api):
    # No PaymentGatewayConfig at all — the webhook loop has nothing to try,
    # so it must reject rather than crash.
    body = _completed_event("cs_test_no_seller", 1)
    response = anon_api.post(
        WEBHOOK_URL, data=body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_sign(body)
    )
    assert response.status_code == 400


def test_stripe_provider_rejects_invalid_signature():
    provider = StripePaymentProvider(secret_key="sk_test_fake", webhook_secret="whsec_test_fake")
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(
            payload=b'{"type": "checkout.session.completed"}',
            headers={"HTTP_STRIPE_SIGNATURE": "not-a-real-signature"},
            query_params={},
        )


def test_stripe_provider_accepts_valid_signature():
    secret = "whsec_test_fake"
    provider = StripePaymentProvider(secret_key="sk_test_fake", webhook_secret=secret)
    payload = b'{"object": "event", "type": "checkout.session.completed", "id": "evt_1"}'
    event = provider.parse_webhook_event(
        payload=payload,
        headers={"HTTP_STRIPE_SIGNATURE": _sign(payload, secret)},
        query_params={},
    )
    assert event["type"] == "checkout.session.completed"
