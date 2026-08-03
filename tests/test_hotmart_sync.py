"""RED tests for `manage.py sync_hotmart_connections` (see design's
"sync = shared reconcile function, two triggers" decision — this command
covers landings whose owner never logs in)."""

import pytest
from django.core.management import call_command

from apps.editor.models import UserTemplate
from apps.hotmart.models import HotmartConnection, HotmartProductLink

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fake_client_by_default(monkeypatch):
    # Test-seam note (design.md): a connection now always carries stored
    # credentials, so the command's build_hotmart_client(connection.get_credentials())
    # would otherwise select RealHotmartClient and attempt a real HTTP call.
    from apps.hotmart.client import FakeHotmartClient

    monkeypatch.setattr(
        "apps.hotmart.management.commands.sync_hotmart_connections.build_hotmart_client",
        lambda credentials: FakeHotmartClient(),
    )


def _state():
    return {"document": {"body": {"children": []}}}


def _connected(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_credentials({"client_id": "id-1", "client_secret": "secret-1"})
    connection.set_tokens(access="a", expires_in=3600)
    connection.save()
    return connection


def _linked(connection, owner, product_id):
    template = UserTemplate.objects.create(
        owner=owner, name=f"Landing {product_id}", state=_state()
    )
    template.publish()
    return HotmartProductLink.objects.create(
        connection=connection,
        user_template=template,
        hotmart_product_id=product_id,
        checkout_url=f"https://hotmart.example.com/checkout/{product_id}",
    )


def test_sync_unpublishes_only_orphaned_links(user, other_user):
    # FakeHotmartClient.list_products() always returns exactly one active
    # product with id "fake-product-1" — link a landing to that id (stays
    # published) and a different id (gets orphaned and unpublished).
    connection = _connected(user)
    kept_link = _linked(connection, user, "fake-product-1")
    orphaned_link = _linked(connection, user, "prod-does-not-exist")

    other_connection = _connected(other_user)
    other_link = _linked(other_connection, other_user, "fake-product-1")

    exit_code = call_command("sync_hotmart_connections")

    assert exit_code == 0
    kept_link.refresh_from_db()
    kept_link.user_template.refresh_from_db()
    assert kept_link.status == HotmartProductLink.Status.ACTIVE
    assert kept_link.user_template.is_published is True

    orphaned_link.refresh_from_db()
    orphaned_link.user_template.refresh_from_db()
    assert orphaned_link.status == HotmartProductLink.Status.UPSTREAM_MISSING
    assert orphaned_link.user_template.is_published is False

    other_link.refresh_from_db()
    other_link.user_template.refresh_from_db()
    assert other_link.status == HotmartProductLink.Status.ACTIVE
    assert other_link.user_template.is_published is True


def test_sync_skips_connections_without_any_links(user):
    HotmartConnection.objects.create(owner=user)

    exit_code = call_command("sync_hotmart_connections")

    assert exit_code == 0
