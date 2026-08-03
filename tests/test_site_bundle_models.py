import pytest
from django.db import IntegrityError, transaction

from apps.editor.models import BundleAsset, SiteBundle

pytestmark = pytest.mark.django_db


def test_site_bundle_is_owner_scoped(user, other_user):
    SiteBundle.objects.create(owner=user, name="mine")
    SiteBundle.objects.create(owner=other_user, name="theirs")
    assert list(SiteBundle.objects.filter(owner=user).values_list("name", flat=True)) == ["mine"]


def test_bundle_asset_path_is_unique_per_bundle(user):
    bundle = SiteBundle.objects.create(owner=user, name="site")
    BundleAsset.objects.create(
        bundle=bundle, path="index.html", content_type="text/html", byte_size=10
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        BundleAsset.objects.create(
            bundle=bundle, path="index.html", content_type="text/html", byte_size=20
        )


def test_same_path_allowed_across_different_bundles(user):
    bundle_a = SiteBundle.objects.create(owner=user, name="a")
    bundle_b = SiteBundle.objects.create(owner=user, name="b")
    BundleAsset.objects.create(
        bundle=bundle_a, path="index.html", content_type="text/html", byte_size=10
    )
    BundleAsset.objects.create(
        bundle=bundle_b, path="index.html", content_type="text/html", byte_size=10
    )
    assert BundleAsset.objects.filter(path="index.html").count() == 2


def test_deleting_bundle_cascades_to_assets(user):
    bundle = SiteBundle.objects.create(owner=user, name="site")
    BundleAsset.objects.create(
        bundle=bundle, path="index.html", content_type="text/html", byte_size=10
    )
    bundle.delete()
    assert BundleAsset.objects.count() == 0
