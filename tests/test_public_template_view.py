import pytest

from apps.editor.models import UserTemplate

pytestmark = pytest.mark.django_db

API_URL = "/api/user-templates/"


def _state(title="Mi negocio", text="Hola"):
    return {
        "document": {
            "head": {"title": title, "metas": [], "links": [], "scripts": []},
            "htmlAttributes": {"lang": "es", "dir": "ltr"},
            "doctype": "html",
            "body": {
                "attributes": {},
                "children": [
                    {
                        "type": "element",
                        "tag": "h1",
                        "attributes": {},
                        "children": [{"type": "text", "value": text}],
                    }
                ],
            },
        },
        "styles": {"variables": {}, "rules": [], "mediaQueries": [], "keyframes": []},
        "components": {},
        "assets": {},
    }


def test_publish_generates_slug_and_public_view_renders(api, user):
    ut = UserTemplate.objects.create(owner=user, name="Mi Template", state=_state())
    response = api.post(f"{API_URL}{ut.id}/publish/")
    assert response.status_code == 200
    assert response.data["is_published"] is True
    slug = response.data["public_slug"]
    assert slug

    public_response = api.get(f"/t/{slug}/")
    assert public_response.status_code == 200
    assert b"Hola" in public_response.content
    assert b"Mi negocio" in public_response.content


def test_unpublished_template_404s(anon_api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state())
    response = anon_api.get(f"/t/{ut.public_slug or 'no-slug'}/")
    assert response.status_code == 404


def test_unpublish_makes_public_url_404(api, anon_api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state())
    api.post(f"{API_URL}{ut.id}/publish/")
    ut.refresh_from_db()
    slug = ut.public_slug

    assert anon_api.get(f"/t/{slug}/").status_code == 200

    api.post(f"{API_URL}{ut.id}/unpublish/")
    assert anon_api.get(f"/t/{slug}/").status_code == 404


def test_republishing_keeps_the_same_slug(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state())
    api.post(f"{API_URL}{ut.id}/publish/")
    ut.refresh_from_db()
    first_slug = ut.public_slug

    api.post(f"{API_URL}{ut.id}/unpublish/")
    api.post(f"{API_URL}{ut.id}/publish/")
    ut.refresh_from_db()
    assert ut.public_slug == first_slug


def test_publish_is_owner_scoped(api, other_api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state())
    response = other_api.post(f"{API_URL}{ut.id}/publish/")
    assert response.status_code == 404
    ut.refresh_from_db()
    assert ut.is_published is False


def test_public_view_never_references_editor_scripts(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state())
    response = api.post(f"{API_URL}{ut.id}/publish/")
    slug = response.data["public_slug"]

    public_response = api.get(f"/t/{slug}/")
    body = public_response.content.decode()
    for script in ("editor-core.js", "editor-ai.js", "autosave.js", "save-template.js"):
        assert script not in body


def test_public_view_includes_opt_in_analytics_tracker(api, user):
    ut = UserTemplate.objects.create(owner=user, name="Tracked", state=_state())
    response = api.post(f"{API_URL}{ut.id}/publish/")
    slug = response.data["public_slug"]

    public_response = api.get(f"/t/{slug}/")
    body = public_response.content.decode()

    assert 'id="analyticsConsent"' in body
    assert 'data-template-slug="' + slug + '"' in body
    assert "/static/analytics/public-tracker.css" in body
    assert "/static/analytics/public-tracker.js" in body


def test_public_view_renders_legacy_styles_rules_document(api, user):
    legacy_state = {
        "document": {
            "head": {"title": "Legacy", "metas": [], "links": [], "scripts": []},
            "htmlAttributes": {"lang": "es", "dir": "ltr"},
            "doctype": "html",
            "body": {
                "attributes": {"class": ["page"]},
                "children": [
                    {
                        "type": "element",
                        "tag": "h1",
                        "attributes": {"class": ["hero-title"]},
                        "children": [{"type": "text", "value": "Legacy content"}],
                    }
                ],
            },
        },
        "styles": {
            "variables": {"--color-primary": "#5b5ce2"},
            "rules": [
                {"selector": ".hero-title", "declarations": {"color": "var(--color-primary)"}}
            ],
            "mediaQueries": [],
            "keyframes": [],
        },
        "components": {},
        "assets": {},
    }
    ut = UserTemplate.objects.create(owner=user, name="Legacy", state=legacy_state)
    response = api.post(f"{API_URL}{ut.id}/publish/")
    slug = response.data["public_slug"]

    public_response = api.get(f"/t/{slug}/")
    assert public_response.status_code == 200
    body = public_response.content.decode()
    assert "Legacy content" in body
    assert ".hero-title { color: var(--color-primary) }" in body
