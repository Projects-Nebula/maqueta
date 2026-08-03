"""RED tests for apps/hotmart/services.py (ensure_fresh_token,
reconcile_products) and the /api/hotmart/products/ endpoint that wires
them together (see design's "Transparent Token Refresh" and
"reconciliation is fail-SAFE" decisions)."""

import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.editor.models import UserTemplate
from apps.hotmart.client import FakeHotmartClient, HotmartClientError, HotmartProduct
from apps.hotmart.models import HotmartConnection, HotmartProductLink
from apps.hotmart.services import HotmartReconnectRequired, ensure_fresh_token, reconcile_products

pytestmark = pytest.mark.django_db

PRODUCTS_URL = "/api/hotmart/products/"


class RaisingRefreshClient(FakeHotmartClient):
    def fetch_token(self):
        raise HotmartClientError("re-exchange rejected upstream")


def _state():
    return {"document": {"body": {"children": []}}}


def _connected(user, *, expired=False):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_credentials({"client_id": "id-1", "client_secret": "secret-1"})
    connection.set_tokens(access="initial-access", expires_in=3600)
    if expired:
        connection.expires_at = timezone.now() - timedelta(seconds=1)
    connection.save()
    return connection


def _linked(connection, *, product_id="prod-1", status=HotmartProductLink.Status.ACTIVE):
    template = UserTemplate.objects.create(owner=connection.owner, name="Landing", state=_state())
    template.publish()
    return HotmartProductLink.objects.create(
        connection=connection,
        user_template=template,
        hotmart_product_id=product_id,
        product_name="Some product",
        checkout_url="https://hotmart.example.com/checkout/prod-1",
        status=status,
    )


class TestEnsureFreshToken:
    def test_returns_current_token_when_not_expired(self, user):
        connection = _connected(user)
        client = FakeHotmartClient()

        token = ensure_fresh_token(connection, client)

        assert token == connection.get_access_token()

    def test_refreshes_transparently_when_expired(self, user):
        connection = _connected(user, expired=True)
        old_access = connection.get_access_token()
        client = FakeHotmartClient()

        token = ensure_fresh_token(connection, client)

        assert token != old_access
        connection.refresh_from_db()
        assert connection.get_access_token() == token
        assert not connection.is_expired

    def test_raises_reconnect_required_when_refresh_fails(self, user):
        connection = _connected(user, expired=True)
        client = RaisingRefreshClient()

        with pytest.raises(HotmartReconnectRequired):
            ensure_fresh_token(connection, client)

    def test_raises_reconnect_required_when_no_credentials_stored(self, user):
        connection = HotmartConnection.objects.create(owner=user)
        client = FakeHotmartClient()

        with pytest.raises(HotmartReconnectRequired):
            ensure_fresh_token(connection, client)


class TestReconcileProducts:
    def test_none_products_is_a_fail_safe_no_op(self, user):
        connection = _connected(user)
        link = _linked(connection)

        reconcile_products(connection, None)

        link.refresh_from_db()
        link.user_template.refresh_from_db()
        assert link.status == HotmartProductLink.Status.ACTIVE
        assert link.user_template.is_published is True

    def test_missing_product_unpublishes_landing(self, user):
        connection = _connected(user)
        link = _linked(connection, product_id="prod-gone")

        reconcile_products(connection, [])

        link.refresh_from_db()
        link.user_template.refresh_from_db()
        assert link.status == HotmartProductLink.Status.UPSTREAM_MISSING
        assert link.user_template.is_published is False

    def test_inactive_product_unpublishes_landing(self, user):
        connection = _connected(user)
        link = _linked(connection, product_id="prod-paused")
        products = [
            HotmartProduct(
                id="prod-paused",
                ucode="ucode-paused",
                name="Paused",
                is_active=False,
                checkout_url="",
            )
        ]

        reconcile_products(connection, products)

        link.refresh_from_db()
        link.user_template.refresh_from_db()
        assert link.status == HotmartProductLink.Status.UPSTREAM_MISSING
        assert link.user_template.is_published is False

    def test_active_product_leaves_landing_untouched(self, user):
        connection = _connected(user)
        link = _linked(connection, product_id="prod-active")
        products = [
            HotmartProduct(
                id="prod-active",
                ucode="ucode-active",
                name="Active",
                is_active=True,
                checkout_url="",
            )
        ]

        reconcile_products(connection, products)

        link.refresh_from_db()
        link.user_template.refresh_from_db()
        assert link.status == HotmartProductLink.Status.ACTIVE
        assert link.user_template.is_published is True

    def test_already_missing_link_is_idempotent(self, user):
        connection = _connected(user)
        link = _linked(
            connection,
            product_id="prod-gone",
            status=HotmartProductLink.Status.UPSTREAM_MISSING,
        )
        link.user_template.unpublish()

        reconcile_products(connection, [])

        link.refresh_from_db()
        link.user_template.refresh_from_db()
        assert link.status == HotmartProductLink.Status.UPSTREAM_MISSING
        assert link.user_template.is_published is False


class TestProductListView:
    # Test-seam note (design.md): a connection now always carries stored
    # credentials, so the old "no platform creds -> Fake" path no longer
    # triggers implicitly — every test here monkeypatches
    # apps.hotmart.views.build_hotmart_client explicitly, defaulting to
    # FakeHotmartClient so no test accidentally makes a real HTTP call.
    @pytest.fixture(autouse=True)
    def _fake_client_by_default(self, monkeypatch):
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client", lambda credentials: FakeHotmartClient()
        )

    def test_not_connected_returns_connected_false_without_upstream_call(self, api, monkeypatch):
        def _boom(credentials):
            raise AssertionError("must not build a Hotmart client when not connected")

        monkeypatch.setattr("apps.hotmart.views.build_hotmart_client", _boom)

        response = api.get(PRODUCTS_URL)

        assert response.status_code == 200
        assert response.data["connected"] is False
        assert response.data["products"] == []

    def test_connected_seller_lists_products(self, api, user):
        _connected(user)

        response = api.get(PRODUCTS_URL)

        assert response.status_code == 200
        assert response.data["connected"] is True
        assert response.data["products"][0]["id"] == "fake-product-1"
        assert response.data["products"][0]["name"] == "Fake Product"

    def test_refresh_failure_returns_409_reconnect(self, api, user, monkeypatch):
        _connected(user, expired=True)
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client", lambda credentials: RaisingRefreshClient()
        )

        response = api.get(PRODUCTS_URL)

        assert response.status_code == 409
        assert response.data["error"] == "reconnect_required"

    def test_no_token_value_appears_in_response_or_logs(self, api, user, caplog):
        connection = _connected(user, expired=True)
        old_access = connection.get_access_token()

        with caplog.at_level(logging.INFO):
            response = api.get(PRODUCTS_URL)

        body = str(response.data)
        assert old_access not in body
        assert old_access not in caplog.text
        connection.refresh_from_db()
        new_access = connection.get_access_token()
        assert new_access not in body
        assert new_access not in caplog.text
