"""Regression coverage for the storefront/payments removal. See
sdd/remove-storefront-payments spec: negative-space acceptance criteria —
routes are gone, and a pre-existing UserTemplate (created via the old
buy-form flow) survives as an ordinary, editable landing once the
storefront app (Product/Order/PaymentGatewayConfig) is deleted."""

import pytest
from django.conf import settings
from django.test import Client

from apps.editor.models import UserTemplate

pytestmark = pytest.mark.django_db


@pytest.fixture
def web_client(user):
    client = Client()
    client.force_login(user)
    return client


def test_storefront_apps_is_not_installed():
    assert "apps.storefront" not in settings.INSTALLED_APPS


def test_products_route_is_gone(web_client):
    response = web_client.get("/productos/")
    assert response.status_code == 404


def test_payment_config_route_is_gone(web_client):
    response = web_client.get("/config/")
    assert response.status_code == 404


def test_checkout_route_is_gone(web_client):
    response = web_client.get("/comprar/1/stripe/")
    assert response.status_code == 404


def test_download_route_is_gone(web_client):
    response = web_client.get("/descargas/tok/")
    assert response.status_code == 404


def test_pre_existing_user_template_survives_and_stays_editable(api, user):
    # Simulates a UserTemplate created in the past via the old buy-form
    # flow: only the (now-deleted) Product/Order/PaymentGatewayConfig rows
    # pointed at it via a /comprar/ CTA, the UserTemplate row itself is an
    # ordinary owner-scoped landing.
    template = UserTemplate.objects.create(
        owner=user,
        name="Ex-storefront landing",
        state={
            "document": {"body": {"attributes": {}, "children": []}, "head": {}},
            "styles": {"variables": {}, "rules": [], "keyframes": []},
            "components": {},
            "assets": {},
            "marker": "ex-storefront",
        },
    )

    detail_url = f"/api/user-templates/{template.id}/"
    get_response = api.get(detail_url)
    assert get_response.status_code == 200

    patch_response = api.patch(detail_url, {"name": "Renamed landing"}, format="json")
    assert patch_response.status_code == 200

    template.refresh_from_db()
    assert template.name == "Renamed landing"
