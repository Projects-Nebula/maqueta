import pytest

from apps.editor.svg_sanitize import SvgSanitizationError, sanitize_svg

VALID_LOGO = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="#ff0000" />
  <path d="M10 10 H 90 V 90 H 10 Z" stroke="black" fill="none" />
</svg>
"""


def test_valid_logo_round_trips():
    cleaned = sanitize_svg(VALID_LOGO)
    assert isinstance(cleaned, bytes)
    assert b"<circle" in cleaned
    assert b"<path" in cleaned


def test_removes_script_element():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg">
        <script>alert(1)</script>
        <circle cx="1" cy="1" r="1" />
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"<script" not in cleaned
    assert b"alert(1)" not in cleaned


def test_removes_event_handler_attributes():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg">
        <circle cx="1" cy="1" r="1" onload="alert(1)" onclick="alert(2)" />
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"onload" not in cleaned
    assert b"onclick" not in cleaned
    assert b"alert" not in cleaned


def test_removes_foreignobject_element():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg">
        <foreignObject><div xmlns="http://www.w3.org/1999/xhtml">html</div></foreignObject>
        <circle cx="1" cy="1" r="1" />
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"foreignObject" not in cleaned
    assert b"<div" not in cleaned


def test_rejects_doctype_entity_xxe():
    data = b"""<?xml version="1.0"?>
    <!DOCTYPE svg [
      <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>"""
    with pytest.raises(SvgSanitizationError):
        sanitize_svg(data)


def test_rejects_billion_laughs():
    data = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <svg xmlns="http://www.w3.org/2000/svg"><text>&lol3;</text></svg>"""
    with pytest.raises(SvgSanitizationError):
        sanitize_svg(data)


def test_removes_external_xlink_href():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <use xlink:href="https://evil.com/x.svg#y" />
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"evil.com" not in cleaned


def test_removes_data_text_html_href():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg">
        <a href="data:text/html,&lt;script&gt;alert(1)&lt;/script&gt;">
          <circle cx="1" cy="1" r="1" />
        </a>
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"data:text/html" not in cleaned


def test_keeps_allowed_asset_prefix_href():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <use xlink:href="/media/icons.svg#check" />
    </svg>"""
    cleaned = sanitize_svg(data, asset_url_prefix="/media/")
    assert b"/media/icons.svg#check" in cleaned


def test_keeps_fragment_only_href():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <use xlink:href="#check" />
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"#check" in cleaned


def test_rejects_unparseable_svg():
    with pytest.raises(SvgSanitizationError):
        sanitize_svg(b"not xml at all <<<")


def test_removes_style_element_and_its_css():
    """A <style> element's text content is copied through verbatim with no
    CSS validation — none of CSS_VALUE_FORBIDDEN's protections apply to it.
    The whole element must be dropped rather than left as an unsanitized
    CSS-exfiltration vector (@import, background: url(...))."""
    data = b"""<svg xmlns="http://www.w3.org/2000/svg">
        <style>@import url(https://evil.com/x.css);</style>
        <circle cx="1" cy="1" r="1" />
    </svg>"""
    cleaned = sanitize_svg(data)
    assert b"<style" not in cleaned
    assert b"evil.com" not in cleaned


def test_rejects_deeply_nested_svg_instead_of_crashing():
    """A well-formed, DOCTYPE-free SVG nested beyond MAX_ELEMENT_DEPTH must
    fail closed with SvgSanitizationError, not an uncaught RecursionError
    from the recursive tree walk."""
    depth = 200
    data = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        + b"<g>" * depth
        + b'<circle cx="1" cy="1" r="1" />'
        + b"</g>" * depth
        + b"</svg>"
    )
    with pytest.raises(SvgSanitizationError):
        sanitize_svg(data)
