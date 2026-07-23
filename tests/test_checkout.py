import pytest
from rest_framework.test import APIClient

from apps.storefront.models import Order, PaymentGatewayConfig, Product
from apps.storefront.payments import FakeStripeProvider

pytestmark = pytest.mark.django_db

URL = "/comprar/{}/{}/"


@pytest.fixture(autouse=True)
def _clear_fake_sessions():
    FakeStripeProvider._sessions.clear()
    yield
    FakeStripeProvider._sessions.clear()


def _enable_gateway(owner, gateway="stripe"):
    """Enabled with NO credentials — build_payment_provider falls back to
    that gateway's Fake* variant, same as any real deployment before the
    seller has actually pasted in real keys via /config."""
    return PaymentGatewayConfig.objects.create(owner=owner, gateway=gateway, is_enabled=True)


def test_checkout_redirects_for_active_product(api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_gateway(user)
    response = api.post(URL.format(product.id, "stripe"))
    assert response.status_code == 302
    assert "session_id=" in response.headers["Location"]


def test_checkout_404s_for_missing_product(anon_api):
    response = anon_api.post(URL.format(999999, "stripe"))
    assert response.status_code == 404


def test_checkout_404s_for_inactive_product(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999, is_active=False)
    _enable_gateway(user)
    response = anon_api.post(URL.format(product.id, "stripe"))
    assert response.status_code == 404


def test_checkout_404s_for_unknown_gateway(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = anon_api.post(URL.format(product.id, "not-a-real-gateway"))
    assert response.status_code == 404


def test_checkout_404s_when_seller_never_enabled_that_gateway(anon_api, user):
    # No PaymentGatewayConfig row at all for this owner+gateway — never
    # let a checkout the seller hasn't turned on be reachable.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = anon_api.post(URL.format(product.id, "stripe"))
    assert response.status_code == 404


def test_checkout_404s_when_seller_disabled_that_gateway(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    PaymentGatewayConfig.objects.create(owner=user, gateway="stripe", is_enabled=False)
    response = anon_api.post(URL.format(product.id, "stripe"))
    assert response.status_code == 404


def test_checkout_works_anonymously(anon_api, user):
    # The whole point: no auth/session needed to buy.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_gateway(user)
    response = anon_api.post(URL.format(product.id, "stripe"))
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
    _enable_gateway(user)
    client = APIClient(enforce_csrf_checks=True)
    client.login(username="alice", password="pw-alice-123")
    response = client.post(URL.format(product.id, "stripe"))
    assert response.status_code == 302


def test_checkout_with_fake_provider_creates_order_immediately(anon_api, user):
    # With no real gateway credentials configured (the default until a
    # seller pastes real keys into /config) there is no real payment server
    # to ever deliver the webhook that normally creates the Order. Without
    # recording it directly from CheckoutView for a fake provider, a buyer
    # would land on the success page and see "Procesando tu pago..." forever
    # (reproduced live: a real browser session got stuck on this exact screen).
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_gateway(user)
    response = anon_api.post(URL.format(product.id, "stripe"))
    assert response.status_code == 302
    session_id = response.headers["Location"].split("session_id=")[-1]
    order = Order.objects.get(gateway="stripe", gateway_session_id=session_id)
    assert order.status == Order.Status.PAID
    assert order.product_id == product.id


def test_checkout_ignores_client_supplied_price(anon_api, user):
    # The price charged always comes from the DB row — the request body is
    # never trusted for it (FEATURE.md 1.6). There's no price field the
    # client can even send here (only the product id is in the URL), which
    # is itself the enforcement: assert the created session's fake amount
    # matches the real DB price regardless of anything else in the request.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    _enable_gateway(user)
    response = anon_api.post(URL.format(product.id, "stripe"), {"price_cents": 1}, format="json")
    assert response.status_code == 302
    session_id = response.headers["Location"].split("session_id=")[-1]
    assert FakeStripeProvider._sessions[session_id]["amount_total"] == 1999


def test_checkout_uses_a_different_owners_gateway_config_correctly(anon_api, user, other_user):
    # Two sellers, each with their own gateway enabled — one seller's buyer
    # must never be affected by another seller's (non-)configuration.
    product = Product.objects.create(owner=other_user, name="Course", price_cents=5000)
    _enable_gateway(other_user, "mercadopago")
    response = anon_api.post(URL.format(product.id, "mercadopago"))
    assert response.status_code == 302
    # user (not other_user) never enabled anything — a checkout for a
    # product THEY owned would still 404, proving no cross-owner fallback.
    own_product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = anon_api.post(URL.format(own_product.id, "mercadopago"))
    assert response.status_code == 404


def test_checkout_legacy_url_without_gateway_falls_back_to_first_enabled(anon_api, user):
    # A buy button baked into a UserTemplate's saved state from before the
    # multi-gateway checkout shipped points at /comprar/<id>/ with no
    # gateway segment (reproduced live: an already-published page 404'd
    # after this session's multi-gateway migration). Must still work.
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    PaymentGatewayConfig.objects.create(owner=user, gateway="wompi", is_enabled=True)
    _enable_gateway(user, "mercadopago")
    response = anon_api.post(f"/comprar/{product.id}/")
    assert response.status_code == 302
    # Deterministic: alphabetically first of the seller's enabled gateways.
    order = Order.objects.get(product=product)
    assert order.gateway == "mercadopago"  # "mercadopago" < "wompi" alphabetically


def test_checkout_legacy_url_404s_when_seller_has_nothing_enabled(anon_api, user):
    product = Product.objects.create(owner=user, name="Ebook", price_cents=1999)
    response = anon_api.post(f"/comprar/{product.id}/")
    assert response.status_code == 404
