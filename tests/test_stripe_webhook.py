import json

import pytest

from apps.storefront.models import Order, Product
from apps.storefront.payments import (
    FakePaymentProvider,
    PaymentProviderError,
    StripePaymentProvider,
)

pytestmark = pytest.mark.django_db

WEBHOOK_URL = "/webhooks/stripe/"


def _completed_event(session_id, product_id):
    return json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "client_reference_id": str(product_id)}},
        }
    ).encode()


@pytest.fixture(autouse=True)
def _clear_fake_sessions():
    FakePaymentProvider._sessions.clear()
    yield
    FakePaymentProvider._sessions.clear()


def test_webhook_creates_order_on_completed_session(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    session = FakePaymentProvider().create_checkout_session(
        product_name=product.name,
        amount_cents=product.price_cents,
        currency="usd",
        success_url="http://testserver/gracias/?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://testserver/cancelado/",
        client_reference_id=str(product.id),
    )

    response = anon_api.post(
        WEBHOOK_URL,
        data=_completed_event(session.id, product.id),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert Order.objects.filter(stripe_session_id=session.id).count() == 1
    order = Order.objects.get(stripe_session_id=session.id)
    assert order.status == Order.Status.PAID
    assert order.amount_cents == 1999
    assert order.product_id == product.id


def test_webhook_is_idempotent_on_replay(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    session = FakePaymentProvider().create_checkout_session(
        product_name=product.name,
        amount_cents=product.price_cents,
        currency="usd",
        success_url="http://testserver/gracias/?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://testserver/cancelado/",
        client_reference_id=str(product.id),
    )
    body = _completed_event(session.id, product.id)

    anon_api.post(WEBHOOK_URL, data=body, content_type="application/json")
    anon_api.post(WEBHOOK_URL, data=body, content_type="application/json")

    assert Order.objects.filter(stripe_session_id=session.id).count() == 1


def test_webhook_sets_download_token_for_digital_product(anon_api, user):
    from django.core.files.base import ContentFile

    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    product.digital_file.save("book.pdf", ContentFile(b"%PDF-1.4\nfake"), save=True)

    session = FakePaymentProvider().create_checkout_session(
        product_name=product.name,
        amount_cents=product.price_cents,
        currency="usd",
        success_url="http://testserver/gracias/?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://testserver/cancelado/",
        client_reference_id=str(product.id),
    )
    anon_api.post(
        WEBHOOK_URL, data=_completed_event(session.id, product.id), content_type="application/json"
    )

    order = Order.objects.get(stripe_session_id=session.id)
    assert order.download_token


def test_webhook_ignores_unrelated_event_types(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    session = FakePaymentProvider().create_checkout_session(
        product_name=product.name,
        amount_cents=product.price_cents,
        currency="usd",
        success_url="http://testserver/gracias/?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://testserver/cancelado/",
        client_reference_id=str(product.id),
    )
    body = json.dumps(
        {"type": "payment_intent.created", "data": {"object": {"id": session.id}}}
    ).encode()

    response = anon_api.post(WEBHOOK_URL, data=body, content_type="application/json")
    assert response.status_code == 200
    assert Order.objects.count() == 0


def test_stripe_provider_rejects_invalid_signature():
    provider = StripePaymentProvider(secret_key="sk_test_fake")
    with pytest.raises(PaymentProviderError):
        provider.parse_webhook_event(
            payload=b'{"type": "checkout.session.completed"}',
            sig_header="not-a-real-signature",
            webhook_secret="whsec_test_fake",
        )
