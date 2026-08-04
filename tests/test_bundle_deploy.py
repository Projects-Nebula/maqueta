import io

import pytest

from apps.editor.models import BundleAsset, SiteBundle
from apps.vercel.client import FakeVercelClient, VercelClientError
from apps.vercel.models import VercelDeployment

pytestmark = pytest.mark.django_db

BUNDLES_URL = "/api/editor/bundles/"


def _bundle_with_index(owner, name="my-site"):
    bundle = SiteBundle.objects.create(owner=owner, name=name)
    asset = BundleAsset.objects.create(
        bundle=bundle, path="index.html", content_type="text/html", byte_size=10
    )
    asset.file.save("index.html", io.BytesIO(b"<html></html>"))
    return bundle


def test_deploy_persists_deployment_and_returns_url(api, user):
    bundle = _bundle_with_index(user)

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/")

    assert response.status_code == 201
    body = response.json()
    assert body["url"].startswith("https://")
    assert VercelDeployment.objects.filter(bundle=bundle).count() == 1


def test_deploy_of_another_users_bundle_returns_404(other_api, user):
    bundle = _bundle_with_index(user)

    response = other_api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/")

    assert response.status_code == 404


def test_deploy_failure_returns_502_and_persists_no_deployment_row(monkeypatch, api, user):
    bundle = _bundle_with_index(user)

    class _FailingClient(FakeVercelClient):
        def create_deployment(self, *, project_name, files):
            raise VercelClientError("boom")

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _FailingClient())

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/")

    assert response.status_code == 502
    assert response.json()["error"] == "deploy_failed"
    assert VercelDeployment.objects.filter(bundle=bundle).count() == 0


def test_redeploy_reuses_the_same_project_id(api, user):
    bundle = _bundle_with_index(user)

    first = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/").json()
    second = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/").json()

    first_deployment = VercelDeployment.objects.get(pk=first["id"])
    second_deployment = VercelDeployment.objects.get(pk=second["id"])
    assert first_deployment.project_id == second_deployment.project_id
    assert first_deployment.deployment_id != second_deployment.deployment_id


def test_anonymous_deploy_is_rejected(anon_api, user):
    bundle = _bundle_with_index(user)

    response = anon_api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/")

    assert response.status_code in (401, 403)


def test_deploy_target_maqueta_publishes_and_sets_hosted_locally(api, user):
    bundle = _bundle_with_index(user)

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/", data={"target": "maqueta"})

    assert response.status_code == 201
    body = response.json()
    assert body["target"] == "maqueta"
    bundle.refresh_from_db()
    assert bundle.is_hosted_locally is True
    assert bundle.public_slug
    assert body["url"].endswith(f"/s/{bundle.public_slug}/")


def test_deploy_target_vercel_unchanged_for_index_html_bundle(api, user):
    bundle = _bundle_with_index(user)

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/", data={"target": "vercel"})

    assert response.status_code == 201
    body = response.json()
    assert body["url"].startswith("https://")
    assert VercelDeployment.objects.filter(bundle=bundle).count() == 1


def test_deploy_target_vercel_rejected_for_non_index_entrypoint(api, user):
    bundle = SiteBundle.objects.create(owner=user, name="my-site", entrypoint_path="home.html")
    asset = BundleAsset.objects.create(
        bundle=bundle, path="home.html", content_type="text/html", byte_size=10
    )
    asset.file.save("home.html", io.BytesIO(b"<html></html>"))

    response = api.post(f"{BUNDLES_URL}{bundle.pk}/deploy/", data={"target": "vercel"})

    assert response.status_code == 400
    assert response.json()["error"] == "vercel_requires_index"
    assert VercelDeployment.objects.filter(bundle=bundle).count() == 0
