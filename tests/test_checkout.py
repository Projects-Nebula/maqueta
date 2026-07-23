import pytest

from apps.storefront.models import Product

pytestmark = pytest.mark.django_db

URL = "/comprar/{}/"


def test_checkout_redirects_for_active_product(api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = api.post(URL.format(product.id))
    assert response.status_code == 302
    assert "session_id=" in response.headers["Location"]


def test_checkout_404s_for_missing_product(anon_api):
    response = anon_api.post(URL.format(999999))
    assert response.status_code == 404


def test_checkout_404s_for_inactive_product(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999, is_active=False)
    response = anon_api.post(URL.format(product.id))
    assert response.status_code == 404


def test_checkout_works_anonymously(anon_api, user):
    # The whole point: no auth/session needed to buy.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = anon_api.post(URL.format(product.id))
    assert response.status_code == 302


def test_checkout_ignores_client_supplied_price(anon_api, user):
    # The price charged always comes from the DB row — the request body is
    # never trusted for it (FEATURE.md 1.6). There's no price field the
    # client can even send here (only the product id is in the URL), which
    # is itself the enforcement: assert the created session's fake amount
    # matches the real DB price regardless of anything else in the request.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    from apps.storefront.payments import FakePaymentProvider

    FakePaymentProvider._sessions.clear()
    response = anon_api.post(URL.format(product.id), {"price_cents": 1}, format="json")
    assert response.status_code == 302
    session_id = response.headers["Location"].split("session_id=")[-1]
    assert FakePaymentProvider._sessions[session_id]["amount_total"] == 1999
