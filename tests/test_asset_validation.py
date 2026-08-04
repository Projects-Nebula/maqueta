"""Threat-matrix tests for apps.editor.asset_validation.

Every case here targets a specific hostile-input class (path traversal,
oversized/malicious files, spoofed extensions, decompression bombs, ...)
this module's validate_bundle() must reject before any bundle asset is
written — proving the rejection, not just exercising the happy path.
"""

import io

import pytest
from PIL import Image

from apps.editor.asset_validation import (
    MAX_BUNDLE_FILE_BYTES,
    MAX_BUNDLE_FILES,
    MAX_BUNDLE_TOTAL_BYTES,
    BundleFile,
    BundleValidationError,
    process_bundle_image,
    resolve_entrypoint,
    validate_bundle,
)
from apps.editor.image_processing import ImageProcessingError


def _png_bytes(width=4, height=4, mode="RGBA", color=(255, 0, 0, 128)):
    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width=4, height=4, color=(255, 0, 0)):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


def _valid_bundle_files(extra=None):
    files = [
        BundleFile(path="index.html", data=b"<html><body>hi</body></html>"),
        BundleFile(path="assets/logo.png", data=_png_bytes()),
    ]
    if extra:
        files.extend(extra)
    return files


# --- 2.1 path traversal --------------------------------------------------


@pytest.mark.parametrize(
    "bad_path",
    [
        "../../etc/passwd",
        "../secret.txt",
        "/etc/passwd",
        "a\\b.css",
        "assets/../../etc/passwd",
        "assets/..\\..\\etc\\passwd",
        "a\x00b.css",
    ],
)
def test_path_traversal_rejected(bad_path):
    files = _valid_bundle_files(extra=[BundleFile(path=bad_path, data=b"body{}")])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "invalid_path"


# --- 2.2 spoofed extension ------------------------------------------------


def test_php_bytes_named_png_rejected():
    files = _valid_bundle_files(
        extra=[BundleFile(path="assets/evil.png", data=b"<?php system($_GET['c']); ?>")]
    )
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "type_mismatch"


def test_elf_bytes_named_css_rejected():
    elf_bytes = b"\x7fELF" + b"\x00" * 60
    files = _valid_bundle_files(extra=[BundleFile(path="assets/evil.css", data=elf_bytes)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "type_mismatch"


def test_pe_bytes_named_js_rejected():
    pe_bytes = b"MZ" + b"\x00" * 60
    files = _valid_bundle_files(extra=[BundleFile(path="assets/evil.js", data=pe_bytes)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "type_mismatch"


# --- 2.3 decompression bomb / oversized image -----------------------------


def test_decompression_bomb_rejected(monkeypatch):
    monkeypatch.setattr("apps.editor.asset_validation.Image.MAX_IMAGE_PIXELS", 100)
    files = _valid_bundle_files(extra=[BundleFile(path="assets/bomb.png", data=_png_bytes(50, 50))])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "invalid_image"


def test_process_bundle_image_rejects_oversized_bytes(monkeypatch):
    monkeypatch.setattr("apps.editor.asset_validation.MAX_UPLOAD_BYTES", 10)
    with pytest.raises(ImageProcessingError):
        process_bundle_image(_png_bytes())


def test_process_bundle_image_rejects_non_oserror_decode_failure(monkeypatch):
    """Pillow's per-format decoders can raise exception types other than
    UnidentifiedImageError/OSError on malformed input (struct.error,
    zlib.error, ValueError, ...). Regression proving those still become a
    clean ImageProcessingError instead of propagating unhandled."""

    def _boom(*args, **kwargs):
        raise ValueError("simulated corrupt-codec failure")

    monkeypatch.setattr("apps.editor.asset_validation.Image.open", _boom)
    with pytest.raises(ImageProcessingError):
        process_bundle_image(_png_bytes())


# --- 2.4 SVG XXE / DOCTYPE / billion laughs / depth --------------------


def test_svg_xxe_rejected():
    data = b"""<?xml version="1.0"?>
    <!DOCTYPE svg [
      <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>"""
    files = _valid_bundle_files(extra=[BundleFile(path="assets/evil.svg", data=data)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "invalid_svg"


def test_svg_billion_laughs_rejected():
    data = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
    ]>
    <svg xmlns="http://www.w3.org/2000/svg"><text>&lol2;</text></svg>"""
    files = _valid_bundle_files(extra=[BundleFile(path="assets/evil.svg", data=data)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "invalid_svg"


def test_svg_excessive_depth_rejected():
    depth = 200
    data = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        + b"<g>" * depth
        + b'<circle cx="1" cy="1" r="1" />'
        + b"</g>" * depth
        + b"</svg>"
    )
    files = _valid_bundle_files(extra=[BundleFile(path="assets/deep.svg", data=data)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "invalid_svg"


def test_valid_svg_is_sanitized_and_kept():
    data = b"""<svg xmlns="http://www.w3.org/2000/svg"><circle cx="1" cy="1" r="1" /></svg>"""
    files = _valid_bundle_files(extra=[BundleFile(path="assets/icon.svg", data=data)])
    assets = validate_bundle(files)
    svg_asset = next(a for a in assets if a.path == "assets/icon.svg")
    assert svg_asset.content_type == "image/svg+xml"
    assert b"<circle" in svg_asset.data


# --- 2.5 caps exceeded -----------------------------------------------------


def test_too_many_files_rejected():
    extra = [BundleFile(path=f"assets/f{i}.css", data=b"body{}") for i in range(MAX_BUNDLE_FILES)]
    files = _valid_bundle_files(extra=extra)
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "too_large"


def test_total_size_cap_exceeded_rejected():
    big = b"a" * (MAX_BUNDLE_TOTAL_BYTES + 1)
    files = _valid_bundle_files(extra=[BundleFile(path="assets/big.css", data=big)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "too_large"


def test_single_file_cap_exceeded_rejected():
    big = b"a" * (MAX_BUNDLE_FILE_BYTES + 1)
    files = _valid_bundle_files(extra=[BundleFile(path="assets/big.css", data=big)])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "too_large"


def test_caps_checked_before_any_asset_content_is_processed(monkeypatch):
    """Nothing about content (image decode, SVG parse) should run once a cap
    is already blown — a single call to process_bundle_image would prove
    per-file processing was reached before the cap check aborted."""

    def _boom(data):
        raise AssertionError("process_bundle_image must not run past a caps rejection")

    monkeypatch.setattr("apps.editor.asset_validation.process_bundle_image", _boom)
    extra = [BundleFile(path=f"assets/f{i}.css", data=b"body{}") for i in range(MAX_BUNDLE_FILES)]
    files = _valid_bundle_files(extra=extra)
    with pytest.raises(BundleValidationError):
        validate_bundle(files)


# --- 2.6 missing entrypoint -------------------------------------------------
#
# validate_bundle() only requires >= 1 HTML file anywhere in the bundle; it
# no longer requires a literal top-level index.html. Entrypoint *selection*
# (which HTML file serves as "/") is resolve_entrypoint()'s job, tested
# separately below.


def test_bundle_with_zero_html_files_rejected():
    files = [BundleFile(path="assets/logo.png", data=_png_bytes())]
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "missing_entrypoint"


def test_empty_bundle_rejected():
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle([])
    assert exc_info.value.code == "missing_entrypoint"


def test_bundle_without_index_html_but_with_other_html_is_accepted():
    files = [BundleFile(path="about.html", data=b"<html>about</html>")]
    assets = validate_bundle(files)
    assert {a.path for a in assets} == {"about.html"}


def test_bundle_with_only_nested_html_is_accepted():
    files = [BundleFile(path="pages/index.html", data=b"<html></html>")]
    assets = validate_bundle(files)
    assert {a.path for a in assets} == {"pages/index.html"}


# --- resolve_entrypoint() ---------------------------------------------------


def test_resolve_entrypoint_auto_selects_top_level_index_html():
    assets = validate_bundle(
        [
            BundleFile(path="index.html", data=b"<html>home</html>"),
            BundleFile(path="about.html", data=b"<html>about</html>"),
        ]
    )
    assert resolve_entrypoint(assets, None) == "index.html"


def test_resolve_entrypoint_accepts_explicit_valid_entrypoint():
    assets = validate_bundle([BundleFile(path="home.html", data=b"<html>home</html>")])
    assert resolve_entrypoint(assets, "home.html") == "home.html"


def test_resolve_entrypoint_requires_selection_when_no_top_level_index():
    assets = validate_bundle(
        [
            BundleFile(path="home.html", data=b"<html>home</html>"),
            BundleFile(path="landing/start.html", data=b"<html>start</html>"),
        ]
    )
    with pytest.raises(BundleValidationError) as exc_info:
        resolve_entrypoint(assets, None)
    assert exc_info.value.code == "entrypoint_required"
    assert exc_info.value.candidates == ["home.html", "landing/start.html"]


def test_resolve_entrypoint_nested_index_html_does_not_auto_satisfy():
    """A nested index.html (e.g. pages/index.html) is NOT a top-level
    entrypoint — resolve_entrypoint must not auto-select it."""
    assets = validate_bundle([BundleFile(path="pages/index.html", data=b"<html></html>")])
    with pytest.raises(BundleValidationError) as exc_info:
        resolve_entrypoint(assets, None)
    assert exc_info.value.code == "entrypoint_required"
    assert exc_info.value.candidates == ["pages/index.html"]


def test_resolve_entrypoint_rejects_invalid_explicit_entrypoint():
    assets = validate_bundle([BundleFile(path="home.html", data=b"<html>home</html>")])
    with pytest.raises(BundleValidationError) as exc_info:
        resolve_entrypoint(assets, "does-not-exist.html")
    assert exc_info.value.code == "invalid_entrypoint"


# --- 2.7 duplicate / case-colliding paths ----------------------------------


def test_case_colliding_duplicate_paths_rejected():
    files = [
        BundleFile(path="index.html", data=b"<html></html>"),
        BundleFile(path="Index.html", data=b"<html>dup</html>"),
    ]
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "duplicate_path"


def test_exact_duplicate_paths_rejected():
    files = [
        BundleFile(path="index.html", data=b"<html></html>"),
        BundleFile(path="assets/logo.png", data=_png_bytes()),
        BundleFile(path="assets/logo.png", data=_png_bytes(color=(0, 255, 0, 255))),
    ]
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "duplicate_path"


# --- deploy-behavior-changing filenames (documentation-like paths) --------


@pytest.mark.parametrize(
    "path",
    [
        "vercel.json",
        "package.json",
        ".htaccess",
        "_middleware.js",
        "middleware.js",
        "api/hello.js",
        "api/nested/hello.js",
        "API/hello.js",
        "Api/Nested/hello.js",
        "Dockerfile",
        "README.sh",
    ],
)
def test_deploy_behavior_changing_files_rejected(path):
    files = _valid_bundle_files(extra=[BundleFile(path=path, data=b"whatever")])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "disallowed_file"


def test_unknown_extension_rejected():
    files = _valid_bundle_files(extra=[BundleFile(path="notes.exe", data=b"MZ\x00\x00")])
    with pytest.raises(BundleValidationError) as exc_info:
        validate_bundle(files)
    assert exc_info.value.code == "disallowed_file"


# --- 2.8 GREEN happy path + process_bundle_image fidelity -----------------


def test_valid_bundle_is_accepted_and_returns_assets():
    files = _valid_bundle_files()
    assets = validate_bundle(files)
    assert {a.path for a in assets} == {"index.html", "assets/logo.png"}


def test_valid_bundle_html_stored_verbatim():
    files = _valid_bundle_files()
    assets = validate_bundle(files)
    html_asset = next(a for a in assets if a.path == "index.html")
    assert html_asset.data == b"<html><body>hi</body></html>"
    assert html_asset.content_type == "text/html"


def test_process_bundle_image_preserves_png_format_and_alpha():
    """Regression guard: process_bundle_image must NOT reuse
    image_processing.process_upload()'s JPEG-forcing shortcut — a
    transparent PNG must stay PNG with alpha intact."""
    data = _png_bytes(mode="RGBA", color=(10, 20, 30, 0))
    encoded, content_type = process_bundle_image(data)
    assert content_type == "image/png"
    result = Image.open(io.BytesIO(encoded))
    assert result.format == "PNG"
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0  # alpha preserved, not flattened


def test_process_bundle_image_preserves_jpeg_format():
    """Regression guard for the other half of the fidelity claim: a JPEG
    input must stay JPEG (the format-preserving branch), not get converted
    to another format or silently re-encoded through the PNG path."""
    data = _jpeg_bytes(color=(10, 20, 30))
    encoded, content_type = process_bundle_image(data)
    assert content_type == "image/jpeg"
    result = Image.open(io.BytesIO(encoded))
    assert result.format == "JPEG"


def test_process_bundle_image_does_not_downscale():
    """image_processing.process_upload() forces MAX_DIMENSION=1600 — the
    bundle-image path must not, since fidelity is the point."""
    data = _png_bytes(width=2000, height=10, mode="RGB", color=(1, 2, 3))
    encoded, _content_type = process_bundle_image(data)
    result = Image.open(io.BytesIO(encoded))
    assert result.width == 2000


def test_svg_asset_url_target_uses_bundle_relative_mode():
    """A bundle-relative href to another asset in the same bundle must
    survive sanitization (asset_url_prefix="" — see svg_sanitize.py)."""
    data = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <use xlink:href="assets/other.svg#x" />
    </svg>"""
    files = _valid_bundle_files(extra=[BundleFile(path="assets/icon.svg", data=data)])
    assets = validate_bundle(files)
    svg_asset = next(a for a in assets if a.path == "assets/icon.svg")
    assert b"assets/other.svg#x" in svg_asset.data
