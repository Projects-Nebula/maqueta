import io

import pytest
from django.contrib.auth import get_user_model

from apps.editor.models import BundleAsset, SiteBundle
from apps.vercel.client import FakeVercelClient, VercelClientError

pytestmark = pytest.mark.django_db

BUNDLES_URL = "/api/editor/bundles/"


def _bundle_with_index(owner, name="my-site"):
    bundle = SiteBundle.objects.create(owner=owner, name=name)
    asset = BundleAsset.objects.create(
        bundle=bundle, path="index.html", content_type="text/html", byte_size=10
    )
    asset.file.save("index.html", io.BytesIO(b"<html></html>"))
    return bundle


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user("staffer", password="pw-staffer-123", is_staff=True)


@pytest.fixture
def staff_api(staff_user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(staff_user)
    return client


def test_admin_can_unpublish_any_bundle(monkeypatch, staff_api, user):
    bundle = _bundle_with_index(user)
    bundle.public_slug = "my-site-abc123"
    bundle.save(update_fields=["public_slug"])

    deleted_projects = []

    class _TrackingClient(FakeVercelClient):
        def delete_project(self, project_name):
            deleted_projects.append(project_name)

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _TrackingClient())

    response = staff_api.post(f"{BUNDLES_URL}{bundle.pk}/unpublish/")

    assert response.status_code == 200
    bundle.refresh_from_db()
    assert bundle.is_active is False
    assert deleted_projects == ["mq-my-site-abc123"]


def test_admin_unpublish_of_never_deployed_bundle_skips_vercel_call(monkeypatch, staff_api, user):
    bundle = _bundle_with_index(user)
    assert not bundle.public_slug

    calls = []

    class _TrackingClient(FakeVercelClient):
        def delete_project(self, project_name):
            calls.append(project_name)

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _TrackingClient())

    response = staff_api.post(f"{BUNDLES_URL}{bundle.pk}/unpublish/")

    assert response.status_code == 200
    bundle.refresh_from_db()
    assert bundle.is_active is False
    assert calls == []


def test_owner_who_is_not_staff_can_unpublish_own_bundle(monkeypatch, api, user):
    bundle = _bundle_with_index(user)
    bundle.public_slug = "my-site-abc123"
    bundle.save(update_fields=["public_slug"])

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: FakeVercelClient())

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/unpublish/")

    assert response.status_code == 200
    bundle.refresh_from_db()
    assert bundle.is_active is False


def test_non_owner_non_staff_cannot_unpublish(other_api, user):
    bundle = _bundle_with_index(user)

    response = other_api.post(f"{BUNDLES_URL}{bundle.pk}/unpublish/")

    assert response.status_code == 403


def test_anonymous_unpublish_is_rejected(anon_api, user):
    bundle = _bundle_with_index(user)

    response = anon_api.post(f"{BUNDLES_URL}{bundle.pk}/unpublish/")

    assert response.status_code in (401, 403)


def test_admin_action_unpublishes_selected_bundles(monkeypatch, rf, staff_user, user):
    """Thin-wrapper test for SiteBundleAdmin.unpublish_selected — the
    underlying unpublish_bundle() behavior already has full RED/GREEN
    coverage above; this only verifies the Django-admin-action wiring
    (queryset iteration + message_user) calls it correctly."""
    from django.contrib import admin as django_admin

    from apps.editor.admin import SiteBundleAdmin

    bundle = _bundle_with_index(user)
    bundle.public_slug = "my-site-def456"
    bundle.save(update_fields=["public_slug"])

    calls = []

    class _TrackingClient(FakeVercelClient):
        def delete_project(self, project_name):
            calls.append(project_name)

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _TrackingClient())

    model_admin = SiteBundleAdmin(SiteBundle, django_admin.site)
    request = rf.post("/admin/editor/sitebundle/")
    request.user = staff_user
    request._messages = _NoopMessages()

    model_admin.unpublish_selected(request, SiteBundle.objects.filter(pk=bundle.pk))

    bundle.refresh_from_db()
    assert bundle.is_active is False
    assert calls == ["mq-my-site-def456"]


class _NoopMessages:
    def add(self, level, message, extra_tags):
        pass


def test_unpublish_failure_returns_502_and_leaves_bundle_active(monkeypatch, staff_api, user):
    bundle = _bundle_with_index(user)
    bundle.public_slug = "my-site-abc123"
    bundle.save(update_fields=["public_slug"])

    class _FailingClient(FakeVercelClient):
        def delete_project(self, project_name):
            raise VercelClientError("boom")

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _FailingClient())

    response = staff_api.post(f"{BUNDLES_URL}{bundle.pk}/unpublish/")

    assert response.status_code == 502
    assert response.json()["error"] == "unpublish_failed"
    bundle.refresh_from_db()
    assert bundle.is_active is True
