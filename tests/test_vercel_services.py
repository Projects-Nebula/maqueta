import pytest

from apps.editor.models import BundleAsset, SiteBundle
from apps.vercel.client import Deployment, FakeVercelClient, VercelClientError
from apps.vercel.models import VercelDeployment
from apps.vercel.services import deploy_bundle

pytestmark = pytest.mark.django_db


def _bundle_with_index(owner, name="my-site"):
    bundle = SiteBundle.objects.create(owner=owner, name=name)
    BundleAsset.objects.create(
        bundle=bundle, path="index.html", content_type="text/html", byte_size=10
    )
    bundle.assets.first().file.save("index.html", __import__("io").BytesIO(b"<html></html>"))
    return bundle


def test_deploy_bundle_persists_deployment_with_url(user):
    bundle = _bundle_with_index(user)

    deployment = deploy_bundle(bundle)

    assert isinstance(deployment, VercelDeployment)
    assert deployment.bundle_id == bundle.pk
    assert deployment.url.startswith("https://")
    assert deployment.deployment_id
    assert deployment.project_id
    assert deployment.state


def test_deploy_bundle_sets_public_slug_once(user):
    bundle = _bundle_with_index(user)
    assert bundle.public_slug is None

    deploy_bundle(bundle)
    bundle.refresh_from_db()
    first_slug = bundle.public_slug
    assert first_slug

    deploy_bundle(bundle)
    bundle.refresh_from_db()
    assert bundle.public_slug == first_slug


def test_redeploy_reuses_the_same_project_id(user):
    bundle = _bundle_with_index(user)

    first = deploy_bundle(bundle)
    second = deploy_bundle(bundle)

    assert first.project_id == second.project_id
    assert first.deployment_id != second.deployment_id


def test_two_bundles_never_share_a_project_id_or_host(user):
    bundle_a = _bundle_with_index(user, name="site-a")
    bundle_b = _bundle_with_index(user, name="site-b")

    deployment_a = deploy_bundle(bundle_a)
    deployment_b = deploy_bundle(bundle_b)

    assert deployment_a.project_id != deployment_b.project_id
    assert deployment_a.url != deployment_b.url


def test_deploy_bundle_raises_and_persists_nothing_on_vercel_error(monkeypatch, user):
    bundle = _bundle_with_index(user)

    class _FailingClient(FakeVercelClient):
        def create_deployment(self, *, project_name, files):
            raise VercelClientError("boom")

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _FailingClient())

    with pytest.raises(VercelClientError):
        deploy_bundle(bundle)

    assert VercelDeployment.objects.count() == 0


def test_deploy_bundle_sends_all_bundle_assets(monkeypatch, user):
    bundle = _bundle_with_index(user)
    BundleAsset.objects.create(
        bundle=bundle, path="assets/logo.png", content_type="image/png", byte_size=3
    )
    bundle.assets.get(path="assets/logo.png").file.save(
        "logo.png", __import__("io").BytesIO(b"png")
    )
    captured = {}

    class _CapturingClient(FakeVercelClient):
        def create_deployment(self, *, project_name, files):
            captured["project_name"] = project_name
            captured["paths"] = sorted(f.path for f in files)
            return Deployment(
                id="dpl-1",
                project_id="prj-1",
                url="dpl-1.vercel.app",
                aliases=["mq-captured.vercel.app"],
                ready_state="READY",
            )

    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: _CapturingClient())

    deploy_bundle(bundle)

    assert captured["paths"] == ["assets/logo.png", "index.html"]
    assert captured["project_name"].startswith("mq-")
