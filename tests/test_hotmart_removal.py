"""Regression coverage for the Hotmart integration removal. See
sdd/remove-hotmart-integration spec: negative-space acceptance criteria —
routes are gone, and a pre-existing UserTemplate (created via the old
Hotmart flow) survives as an ordinary, editable landing once its
HotmartProductLink metadata is deleted along with the app."""

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


def test_hotmart_apps_is_not_installed():
    assert "apps.hotmart" not in settings.INSTALLED_APPS


def test_hotmart_web_route_is_gone(web_client):
    response = web_client.get("/hotmart/")
    assert response.status_code == 404


def test_hotmart_api_route_is_gone(web_client):
    response = web_client.get("/api/hotmart/")
    assert response.status_code == 404


def test_pre_existing_user_template_survives_and_stays_editable(api, user):
    # Simulates a UserTemplate created in the past via the old Hotmart flow:
    # only the (now-deleted) HotmartProductLink metadata pointed at it, the
    # UserTemplate row itself is an ordinary owner-scoped landing.
    template = UserTemplate.objects.create(
        owner=user,
        name="Ex-Hotmart landing",
        state={
            "document": {"body": {"attributes": {}, "children": []}, "head": {}},
            "styles": {"variables": {}, "rules": [], "keyframes": []},
            "components": {},
            "assets": {},
            "marker": "ex-hotmart",
        },
    )

    detail_url = f"/api/user-templates/{template.id}/"
    get_response = api.get(detail_url)
    assert get_response.status_code == 200

    patch_response = api.patch(detail_url, {"name": "Renamed landing"}, format="json")
    assert patch_response.status_code == 200

    template.refresh_from_db()
    assert template.name == "Renamed landing"
