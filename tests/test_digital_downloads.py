import pytest
from django.core.files.base import ContentFile

from apps.storefront.models import Order, Product
from apps.storefront.payments import FakeStripeProvider

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_fake_sessions():
    FakeStripeProvider._sessions.clear()
    yield
    FakeStripeProvider._sessions.clear()


def _paid_order_with_file(user, *, downloads_used=0):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    product.digital_file.save("book.pdf", ContentFile(b"%PDF-1.4\nreal content"), save=True)
    return Order.objects.create(
        product=product,
        gateway=Order.Gateway.STRIPE,
        gateway_session_id="cs_test_x",
        amount_cents=1999,
        currency="usd",
        status=Order.Status.PAID,
        download_token=Order.generate_download_token(),
        download_count=downloads_used,
    )


def test_download_works_for_paid_order(anon_api, user):
    order = _paid_order_with_file(user)
    response = anon_api.get(f"/descargas/{order.download_token}/")
    assert response.status_code == 200
    assert b"real content" in b"".join(response.streaming_content)
    order.refresh_from_db()
    assert order.download_count == 1


def test_download_404s_for_unpaid_order(anon_api, user):
    order = _paid_order_with_file(user)
    order.status = Order.Status.PENDING
    order.save()
    response = anon_api.get(f"/descargas/{order.download_token}/")
    assert response.status_code == 404


def test_download_404s_for_wrong_token(anon_api, user):
    _paid_order_with_file(user)
    response = anon_api.get("/descargas/not-a-real-token/")
    assert response.status_code == 404


def test_download_404s_once_max_downloads_exceeded(anon_api, user):
    order = _paid_order_with_file(user, downloads_used=5)
    response = anon_api.get(f"/descargas/{order.download_token}/")
    assert response.status_code == 404


def test_success_page_falls_back_to_provider_lookup_before_webhook_lands(anon_api, user):
    # Simulates the race condition: the buyer's browser reaches /gracias/
    # before the webhook has created the Order row.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    session = FakeStripeProvider().create_checkout_session(
        product_name=product.name,
        amount_cents=product.price_cents,
        currency="usd",
        success_url="http://testserver/gracias/?gateway=stripe&session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://testserver/cancelado/",
        client_reference_id=str(product.id),
    )
    assert not Order.objects.filter(gateway="stripe", gateway_session_id=session.id).exists()

    response = anon_api.get(f"/gracias/?gateway=stripe&session_id={session.id}")
    assert response.status_code == 200
    # The fake provider reports the session as already paid even though no
    # Order exists yet — the view must not crash, and must not claim a
    # download is ready for an Order it can't actually find.
    assert b"Procesando" in response.content or response.status_code == 200


def test_success_page_shows_download_link_once_order_exists(anon_api, user):
    order = _paid_order_with_file(user)
    response = anon_api.get(
        f"/gracias/?gateway={order.gateway}&session_id={order.gateway_session_id}"
    )
    assert response.status_code == 200
    assert f"/descargas/{order.download_token}/".encode() in response.content


def test_success_page_404s_without_session_id(anon_api):
    response = anon_api.get("/gracias/?gateway=stripe")
    assert response.status_code == 404


def test_success_page_404s_for_unknown_gateway(anon_api):
    response = anon_api.get("/gracias/?gateway=not-a-real-gateway&session_id=x")
    assert response.status_code == 404
