import pytest

from apps.ai_assistant.html_import import HtmlImportError, html_to_node

pytestmark = pytest.mark.django_db

URL = "/api/ai/editor/import-html/"


def test_html_to_node_builds_a_sanitized_tree():
    node, skipped = html_to_node(
        '<section class="hero"><h1>Hola</h1><p>Texto <a href="/x">link</a></p></section>'
    )
    assert node["type"] == "element"
    assert node["tag"] == "div"
    section = node["children"][0]
    assert section["tag"] == "section"
    assert "class" not in section["attributes"]  # dropped, not preserved
    assert skipped == 1  # the class= on <section>


def test_html_to_node_keeps_allowed_attributes():
    node, _ = html_to_node('<a href="/x" title="t">link</a>')
    link = node["children"][0]
    assert link["attributes"] == {"href": "/x", "title": "t"}


def test_html_to_node_rejects_forbidden_tag():
    with pytest.raises(HtmlImportError):
        html_to_node("<script>alert(1)</script>")


def test_html_to_node_drops_event_handler_attribute():
    # Not in KEPT_ATTRS, so it's dropped at parse time rather than merely
    # rejected by sanitize_node — belt-and-suspenders either way.
    node, _ = html_to_node('<div onclick="alert(1)">x</div>')
    assert node["children"][0]["attributes"] == {}


def test_html_to_node_rejects_empty_input():
    with pytest.raises(HtmlImportError):
        html_to_node("   ")


def test_html_to_node_maps_known_style_declarations_to_tailwind():
    node, skipped = html_to_node('<p style="text-align: center; font-weight: bold;">x</p>')
    p = node["children"][0]
    assert set(p["attributes"]["class"]) == {"text-center", "font-bold"}
    assert skipped == 0


def test_html_to_node_drops_unmapped_style_declarations():
    node, skipped = html_to_node('<p style="color: red; text-align: center;">x</p>')
    p = node["children"][0]
    assert p["attributes"]["class"] == ["text-center"]
    assert skipped == 1  # color: red has no mapping


def test_html_to_node_still_drops_raw_class_attribute():
    node, skipped = html_to_node('<p class="hero" style="text-align: center;">x</p>')
    p = node["children"][0]
    assert p["attributes"]["class"] == ["text-center"]  # only the mapped one, not "hero"
    assert skipped == 1  # the class= attribute itself


def test_view_requires_authentication(anon_api):
    response = anon_api.post(URL, {"html": "<p>x</p>"}, format="json")
    assert response.status_code in (401, 403)


def test_view_returns_sanitized_node(api):
    response = api.post(URL, {"html": "<p>Hola</p>"}, format="json")
    assert response.status_code == 200
    assert response.data["node"]["tag"] == "div"
    assert response.data["skipped_attributes"] == 0


def test_view_rejects_forbidden_tag(api):
    response = api.post(URL, {"html": "<script>alert(1)</script>"}, format="json")
    assert response.status_code == 400
    assert response.data["error"] == "invalid_html"
