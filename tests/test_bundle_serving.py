"""Security-critical coverage for PublicBundleAssetView — GET /s/<slug>/...

The load-bearing control here is the per-response `Content-Security-Policy:
sandbox ...` header WITHOUT `allow-same-origin` (see design.md): seller
HTML/JS is admitted verbatim and served from maqueta's own origin, so this
header is what keeps a malicious script from reading document.cookie,
calling same-origin /api/... with the visitor's ambient session, or
registering a service worker. Every test that asserts this header's exact
shape is a regression guard against silently weakening or dropping it.
"""

import io

import pytest

from apps.editor.models import BundleAsset, SiteBundle

pytestmark = pytest.mark.django_db


def _add_asset(bundle, path, data, content_type):
    asset = BundleAsset.objects.create(
        bundle=bundle, path=path, content_type=content_type, byte_size=len(data)
    )
    asset.file.save(path.rsplit("/", 1)[-1], io.BytesIO(data))
    return asset


def _published_bundle(owner, entrypoint="index.html", slug="my-site-abc123"):
    bundle = SiteBundle.objects.create(
        owner=owner,
        name="site",
        entrypoint_path=entrypoint,
        is_hosted_locally=True,
        public_slug=slug,
    )
    _add_asset(bundle, entrypoint, b"<html><body>home</body></html>", "text/html")
    return bundle


def _unpublished_bundle(owner, slug="my-site-unpub"):
    bundle = SiteBundle.objects.create(
        owner=owner,
        name="site",
        entrypoint_path="index.html",
        is_hosted_locally=False,
        public_slug=slug,
    )
    _add_asset(bundle, "index.html", b"<html></html>", "text/html")
    return bundle


# --- 4.1 404 boundaries ------------------------------------------------------


def test_unpublished_bundle_404s(anon_api, user):
    bundle = _unpublished_bundle(user)
    response = anon_api.get(f"/s/{bundle.public_slug}/")
    assert response.status_code == 404


def test_unpublish_makes_public_url_404(anon_api, user):
    bundle = _published_bundle(user)
    assert anon_api.get(f"/s/{bundle.public_slug}/").status_code == 200

    bundle.is_hosted_locally = False
    bundle.save(update_fields=["is_hosted_locally"])

    assert anon_api.get(f"/s/{bundle.public_slug}/").status_code == 404


def test_inactive_bundle_404s(anon_api, user):
    bundle = _published_bundle(user)
    bundle.is_active = False
    bundle.save(update_fields=["is_active"])

    response = anon_api.get(f"/s/{bundle.public_slug}/")
    assert response.status_code == 404


def test_unknown_slug_404s(anon_api):
    response = anon_api.get("/s/no-such-bundle/")
    assert response.status_code == 404


def test_missing_path_404s(anon_api, user):
    bundle = _published_bundle(user)
    response = anon_api.get(f"/s/{bundle.public_slug}/does-not-exist.html")
    assert response.status_code == 404


def test_404_body_is_indistinguishable_across_causes(anon_api, user):
    """Missing path, unpublished bundle, and unknown slug must not let a
    visitor tell "exists but unpublished" apart from "path not found" apart
    from "slug unknown" — same shape, no leaking detail."""
    published = _published_bundle(user, slug="pub-slug")
    unpublished = _unpublished_bundle(user, slug="unpub-slug")

    missing_path_response = anon_api.get(f"/s/{published.public_slug}/nope.html")
    unpublished_response = anon_api.get(f"/s/{unpublished.public_slug}/")
    unknown_slug_response = anon_api.get("/s/totally-unknown-slug/")

    assert missing_path_response.status_code == 404
    assert unpublished_response.status_code == 404
    assert unknown_slug_response.status_code == 404
    bodies = {
        missing_path_response.content,
        unpublished_response.content,
        unknown_slug_response.content,
    }
    assert len(bodies) == 1


# --- 4.1 path resolution -----------------------------------------------------


def test_root_path_resolves_to_entrypoint(anon_api, user):
    bundle = _published_bundle(user, entrypoint="about.html")
    response = anon_api.get(f"/s/{bundle.public_slug}/")
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"<html><body>home</body></html>"


def test_relative_asset_resolves(anon_api, user):
    bundle = _published_bundle(user)
    _add_asset(bundle, "assets/logo.png", b"\x89PNG-bytes", "image/png")

    response = anon_api.get(f"/s/{bundle.public_slug}/assets/logo.png")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"\x89PNG-bytes"
    assert response["Content-Type"] == "image/png"


# --- 4.2 security headers -----------------------------------------------------


def test_csp_sandbox_header_present_without_allow_same_origin(anon_api, user):
    bundle = _published_bundle(user)
    response = anon_api.get(f"/s/{bundle.public_slug}/")

    csp = response["Content-Security-Policy"]
    assert "sandbox" in csp
    assert "allow-same-origin" not in csp


def test_x_content_type_options_nosniff(anon_api, user):
    bundle = _published_bundle(user)
    response = anon_api.get(f"/s/{bundle.public_slug}/")
    assert response["X-Content-Type-Options"] == "nosniff"


def test_no_set_cookie_header(anon_api, user):
    bundle = _published_bundle(user)
    response = anon_api.get(f"/s/{bundle.public_slug}/")
    assert "Set-Cookie" not in response


def test_content_type_matches_stored_value(anon_api, user):
    bundle = _published_bundle(user)
    _add_asset(bundle, "style.css", b"body{color:red}", "text/css")

    response = anon_api.get(f"/s/{bundle.public_slug}/style.css")

    assert response["Content-Type"] == "text/css"


# --- 4.3 traversal + throttle -------------------------------------------------


@pytest.mark.parametrize(
    "traversal_path",
    [
        "../../etc/passwd",
        "assets/../../etc/passwd",
        "%2e%2e/%2e%2e/etc/passwd",
    ],
)
def test_path_traversal_404s(anon_api, user, traversal_path):
    bundle = _published_bundle(user)
    response = anon_api.get(f"/s/{bundle.public_slug}/{traversal_path}")
    assert response.status_code == 404


def test_throttle_enforced(anon_api, user):
    # bundle_serve is rate-limited at 120/m (config/settings/base.py); same
    # pattern as test_ai_transform.py's rate-limit test — exhaust the
    # configured bucket, then confirm the next request 429s.
    bundle = _published_bundle(user)

    for _ in range(120):
        response = anon_api.get(f"/s/{bundle.public_slug}/")
        assert response.status_code == 200

    throttled = anon_api.get(f"/s/{bundle.public_slug}/")
    assert throttled.status_code == 429
