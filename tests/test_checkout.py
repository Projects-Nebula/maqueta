import pytest
from rest_framework.test import APIClient

from apps.storefront.models import Order, Product

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


def test_checkout_works_for_a_logged_in_session_without_csrf_header(user):
    # api/anon_api use force_authenticate, which bypasses DRF's real
    # auth+CSRF pipeline entirely and would never have caught this: a real
    # browser session (e.g. the product's own owner, logged into the editor,
    # clicking their own "Comprar" button) goes through DRF's
    # SessionAuthentication, which enforces its OWN CSRF check independent
    # of the view's @csrf_exempt — a plain HTML <form method="post"> with no
    # CSRF token/header used to get rejected with 403 for exactly this user.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    client = APIClient(enforce_csrf_checks=True)
    client.login(username="alice", password="pw-alice-123")
    response = client.post(URL.format(product.id))
    assert response.status_code == 302


def test_checkout_with_fake_provider_creates_order_immediately(anon_api, user):
    # In dev/test (PAYMENT_PROVIDER=fake, the default without real Stripe
    # keys) there is no real Stripe server to ever deliver the webhook that
    # normally creates the Order. Without recording it directly from
    # CheckoutView for this provider, a buyer would land on the success page
    # and see "Procesando tu pago..." forever, since nothing else would ever
    # create the row (reproduced live: a real browser session got stuck on
    # this exact screen).
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = anon_api.post(URL.format(product.id))
    assert response.status_code == 302
    session_id = response.headers["Location"].split("session_id=")[-1]
    order = Order.objects.get(stripe_session_id=session_id)
    assert order.status == Order.Status.PAID
    assert order.product_id == product.id


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
