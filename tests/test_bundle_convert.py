import io

import pytest

from apps.editor.models import BundleAsset, SiteBundle

pytestmark = pytest.mark.django_db

BUNDLES_URL = "/api/editor/bundles/"


def _bundle_with_index(owner, name="my-site"):
    bundle = SiteBundle.objects.create(owner=owner, name=name)
    asset = BundleAsset.objects.create(
        bundle=bundle, path="index.html", content_type="text/html", byte_size=10
    )
    asset.file.save("index.html", io.BytesIO(b"<html></html>"))
    return bundle


def test_convert_returns_501_conversion_unavailable(api, user):
    bundle = _bundle_with_index(user)

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/convert/")

    assert response.status_code == 501
    assert response.json()["error"] == "conversion_unavailable"


def test_convert_of_another_users_bundle_returns_404(other_api, user):
    bundle = _bundle_with_index(user)

    response = other_api.post(f"{BUNDLES_URL}{bundle.pk}/convert/")

    assert response.status_code == 404


def test_anonymous_convert_is_rejected(anon_api, user):
    bundle = _bundle_with_index(user)

    response = anon_api.post(f"{BUNDLES_URL}{bundle.pk}/convert/")

    assert response.status_code in (401, 403)
