"""Provider-level and checkout-level coverage for the 7 non-Stripe gateways
(Stripe itself is covered in depth by test_checkout.py/test_stripe_webhook.py,
the reference implementation). Depth intentionally varies by gateway
confidence (see PAYMENTS.md 2.1-2.8):

- Mercado Pago, Wompi, PayU, ePayco: pure local HMAC/checksum verification,
  no network — both accept-valid and reject-invalid signature paths are
  fully testable and tested here.
- PayPal, Braintree: verification is a real SDK/API call — network is
  mocked (monkeypatch), never hits a real API from a test.
- Bold: parse_webhook_event deliberately always raises (spec unconfirmed,
  see payments.py) — the only assertion possible is that it does exactly
  that, not that it's "working".

Every gateway also gets one checkout-creates-a-fake-session-and-records-
an-order test, mirroring the Stripe fake-provider regression test.
"""

import hashlib
import hmac
import json

import pytest

from apps.storefront.models import Order, PaymentGatewayConfig, Product
from apps.storefront.payments import (
    BoldPaymentProvider,
    EpaycoPaymentProvider,
    FakeBoldProvider,
    FakeBraintreeProvider,
    FakeEpaycoProvider,
    FakeMercadoPagoProvider,
    FakePayPalProvider,
    FakePayUProvider,
    FakeWompiProvider,
    MercadoPagoPaymentProvider,
    PaymentProviderError,
    PayUPaymentProvider,
    WompiPaymentProvider,
)

pytestmark = pytest.mark.django_db

CHECKOUT_URL = "/comprar/{}/{}/"


@pytest.fixture(autouse=True)
def _clear_all_fake_sessions():
    for cls in (
        FakeMercadoPagoProvider,
        FakePayPalProvider,
        FakeBraintreeProvider,
        FakeWompiProvider,
        FakePayUProvider,
        FakeEpaycoProvider,
        FakeBoldProvider,
    ):
        cls._sessions.clear()
    yield


@pytest.mark.parametrize(
    "gateway",
    ["mercadopago", "paypal", "braintree", "wompi", "payu", "epayco", "bold"],
)
def test_checkout_with_fake_provider_creates_order_immediately(anon_api, user, gateway):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    PaymentGatewayConfig.objects.create(owner=user, gateway=gateway, is_enabled=True)
    response = anon_api.post(CHECKOUT_URL.format(product.id, gateway))
    assert response.status_code == 302
    order = Order.objects.get(gateway=gateway)
    assert order.status == Order.Status.PAID
    assert order.product_id == product.id


# --- Mercado Pago: local HMAC-SHA256 (x-signature: ts=...,v1=...) ----------


def test_mercadopago_accepts_valid_signature():
    secret = "mp_test_secret"
    provider = MercadoPagoPaymentProvider(access_token="TEST-token", webhook_secret=secret)
    data_id = "123456"
    request_id = "req-1"
    ts = "1700000000"
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    payload = json.dumps({"type": "payment", "data": {"id": data_id}}).encode()

    event = provider.parse_webhook_event(
        payload=payload,
        headers={"HTTP_X_SIGNATURE": f"ts={ts},v1={v1}", "HTTP_X_REQUEST_ID": request_id},
        query_params={"data.id": data_id},
    )
    assert event["type"] == "payment"


def test_mercadopago_rejects_invalid_signature():
    provider = MercadoPagoPaymentProvider(
        access_token="TEST-token", webhook_secret="mp_test_secret"
    )
    payload = json.dumps({"type": "payment", "data": {"id": "123456"}}).encode()
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(
            payload=payload,
            headers={"HTTP_X_SIGNATURE": "ts=1700000000,v1=not-real", "HTTP_X_REQUEST_ID": "req-1"},
            query_params={"data.id": "123456"},
        )


# --- Wompi: SHA256 checksum over documented event properties ---------------


def test_wompi_accepts_valid_checksum():
    events_secret = "wompi_events_secret"
    provider = WompiPaymentProvider(
        public_key="pub",
        private_key="priv",
        integrity_secret="integrity",
        events_secret=events_secret,
    )
    event = {
        "data": {"transaction": {"id": "tx_1", "status": "APPROVED", "reference": "ref_1"}},
        "signature": {"properties": ["transaction.id", "transaction.status"]},
        "timestamp": 1700000000,
    }
    concatenated = "tx_1APPROVED1700000000" + events_secret
    checksum = hashlib.sha256(concatenated.encode()).hexdigest()
    event["signature"]["checksum"] = checksum

    result = provider.parse_webhook_event(
        payload=json.dumps(event).encode(), headers={}, query_params={}
    )
    assert result["data"]["transaction"]["reference"] == "ref_1"


def test_wompi_rejects_invalid_checksum():
    provider = WompiPaymentProvider(
        public_key="pub",
        private_key="priv",
        integrity_secret="integrity",
        events_secret="events_secret",
    )
    event = {
        "data": {"transaction": {"id": "tx_1", "status": "APPROVED"}},
        "signature": {"properties": ["transaction.id"], "checksum": "not-real"},
        "timestamp": 1700000000,
    }
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(
            payload=json.dumps(event).encode(), headers={}, query_params={}
        )


# --- PayU: MD5 over ApiKey~merchantId~referenceCode~amount~currency etc ----


def test_payu_accepts_valid_confirmation_signature():
    provider = PayUPaymentProvider(
        merchant_id="500000", account_id="500001", api_key="test_api_key"
    )
    fields = {
        "reference_sale": "payu_ref_1",
        "value": "10.00",
        "currency": "COP",
        "state_pol": "4",
    }
    sign_source = (
        f"{provider.api_key}~{provider.merchant_id}~{fields['reference_sale']}~"
        f"{fields['value']}~{fields['currency']}~{fields['state_pol']}"
    )
    fields["sign"] = hashlib.md5(sign_source.encode()).hexdigest()  # noqa: S324
    from urllib.parse import urlencode

    payload = urlencode(fields).encode()

    event = provider.parse_webhook_event(payload=payload, headers={}, query_params={})
    assert event["reference_sale"] == "payu_ref_1"


def test_payu_rejects_invalid_confirmation_signature():
    provider = PayUPaymentProvider(
        merchant_id="500000", account_id="500001", api_key="test_api_key"
    )
    from urllib.parse import urlencode

    payload = urlencode(
        {
            "reference_sale": "payu_ref_1",
            "value": "10.00",
            "currency": "COP",
            "state_pol": "4",
            "sign": "bad",
        }
    ).encode()
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(payload=payload, headers={}, query_params={})


# --- ePayco: SHA256 over p_cust_id_cliente^p_key^ref^tx^amount^currency ----


def test_epayco_accepts_valid_confirmation_signature():
    provider = EpaycoPaymentProvider(
        public_key="pub", p_key="test_p_key", p_cust_id_cliente="12345"
    )
    fields = {
        "x_ref_payco": "ref_1",
        "x_transaction_id": "tx_1",
        "x_amount": "10.00",
        "x_currency_code": "COP",
    }
    sign_source = (
        f"{provider.p_cust_id_cliente}^{provider.p_key}^{fields['x_ref_payco']}^"
        f"{fields['x_transaction_id']}^{fields['x_amount']}^{fields['x_currency_code']}"
    )
    fields["x_signature"] = hashlib.sha256(sign_source.encode()).hexdigest()
    from urllib.parse import urlencode

    payload = urlencode(fields).encode()

    event = provider.parse_webhook_event(payload=payload, headers={}, query_params={})
    assert event["x_ref_payco"] == "ref_1"


def test_epayco_rejects_invalid_confirmation_signature():
    provider = EpaycoPaymentProvider(
        public_key="pub", p_key="test_p_key", p_cust_id_cliente="12345"
    )
    from urllib.parse import urlencode

    payload = urlencode(
        {
            "x_ref_payco": "ref_1",
            "x_transaction_id": "tx_1",
            "x_amount": "10.00",
            "x_currency_code": "COP",
            "x_signature": "bad",
        }
    ).encode()
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(payload=payload, headers={}, query_params={})


# --- PayPal: verification is a real API call, mocked here -----------------


def test_paypal_webhook_accepts_when_api_verification_succeeds(monkeypatch):
    from apps.storefront import payments as payments_module

    class _FakeResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    def _fake_post(url, **kwargs):
        if "oauth2/token" in url:
            return _FakeResponse({"access_token": "fake-token"})
        if "verify-webhook-signature" in url:
            return _FakeResponse({"verification_status": "SUCCESS"})
        raise AssertionError(f"unexpected POST {url}")

    import requests

    monkeypatch.setattr(requests, "post", _fake_post)

    provider = payments_module.PayPalPaymentProvider(
        client_id="cid", client_secret="csecret", webhook_id="wh_1"
    )
    event = provider.parse_webhook_event(
        payload=b'{"id": "evt_1"}',
        headers={
            "HTTP_PAYPAL_TRANSMISSION_ID": "t1",
            "HTTP_PAYPAL_TRANSMISSION_TIME": "2026-01-01T00:00:00Z",
            "HTTP_PAYPAL_CERT_URL": "https://api.paypal.com/cert",
            "HTTP_PAYPAL_AUTH_ALGO": "SHA256withRSA",
            "HTTP_PAYPAL_TRANSMISSION_SIG": "sig",
        },
        query_params={},
    )
    assert event["id"] == "evt_1"


def test_paypal_webhook_rejects_when_api_verification_fails(monkeypatch):
    import requests

    class _FakeResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    def _fake_post(url, **kwargs):
        if "oauth2/token" in url:
            return _FakeResponse({"access_token": "fake-token"})
        return _FakeResponse({"verification_status": "FAILURE"})

    monkeypatch.setattr(requests, "post", _fake_post)

    from apps.storefront.payments import PayPalPaymentProvider

    provider = PayPalPaymentProvider(client_id="cid", client_secret="csecret", webhook_id="wh_1")
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(
            payload=b'{"id": "evt_1"}',
            headers={
                "HTTP_PAYPAL_TRANSMISSION_ID": "t1",
                "HTTP_PAYPAL_TRANSMISSION_TIME": "2026-01-01T00:00:00Z",
                "HTTP_PAYPAL_CERT_URL": "https://api.paypal.com/cert",
                "HTTP_PAYPAL_AUTH_ALGO": "SHA256withRSA",
                "HTTP_PAYPAL_TRANSMISSION_SIG": "sig",
            },
            query_params={},
        )


# --- Braintree: the SDK verifies its own webhooks --------------------------


def test_braintree_webhook_uses_sdk_verification(monkeypatch):
    from apps.storefront.payments import BraintreePaymentProvider

    class _FakeTransaction:
        id = "txn_1"
        status = "settled"

    class _FakeNotification:
        kind = "transaction_disbursed"
        transaction = _FakeTransaction()

    class _FakeWebhookNotificationGateway:
        def parse(self, signature, payload):
            assert signature == "sig"
            assert payload == "payload"
            return _FakeNotification()

    class _FakeGateway:
        webhook_notification = _FakeWebhookNotificationGateway()

    provider = BraintreePaymentProvider(merchant_id="m", public_key="pub", private_key="priv")
    monkeypatch.setattr(provider, "_gateway", lambda: _FakeGateway())

    from urllib.parse import urlencode

    payload = urlencode({"bt_signature": "sig", "bt_payload": "payload"}).encode()
    event = provider.parse_webhook_event(payload=payload, headers={}, query_params={})
    assert event["transaction_id"] == "txn_1"
    assert event["status"] == "settled"


def test_braintree_webhook_propagates_sdk_rejection(monkeypatch):
    from apps.storefront.payments import BraintreePaymentProvider

    class _FakeWebhookNotificationGateway:
        def parse(self, signature, payload):
            raise Exception("invalid signature")

    class _FakeGateway:
        webhook_notification = _FakeWebhookNotificationGateway()

    provider = BraintreePaymentProvider(merchant_id="m", public_key="pub", private_key="priv")
    monkeypatch.setattr(provider, "_gateway", lambda: _FakeGateway())

    from urllib.parse import urlencode

    payload = urlencode({"bt_signature": "bad", "bt_payload": "payload"}).encode()
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(payload=payload, headers={}, query_params={})


# --- Bold: unverified spec, must always refuse rather than pretend to work -


def test_bold_parse_webhook_event_always_raises():
    provider = BoldPaymentProvider(api_key="k", secret_key="s")
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(payload=b"{}", headers={}, query_params={})


def test_bold_retrieve_session_always_raises():
    provider = BoldPaymentProvider(api_key="k", secret_key="s")
    with pytest.raises(PaymentProviderError):
        provider.retrieve_session("any-id")
