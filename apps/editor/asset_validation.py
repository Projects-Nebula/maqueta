"""Validate and normalize an uploaded site bundle (HTML + asset files).

Shared ingestion layer for both this change's deploy-as-is flow and
site-bundle-import's future convert-to-editable flow (PR3/4, not built
here) — the same SiteBundle/BundleAsset models and this validation pass
serve both paths, so the flows diverge only in what they do with an
already-validated bundle. Both paths call ``validate_bundle()`` once;
nothing downstream re-validates.

Threat model: every file in the upload is fully attacker-controlled —
arbitrary bytes, arbitrary (possibly hostile) paths, arbitrary declared
extensions. Defense in depth, checked in this order for every candidate
file:

1. cheap, whole-bundle caps (file count, total size) before any per-file
   work — a resource-exhaustion attempt is rejected before it costs CPU.
2. path hardening — reject traversal, absolute paths, backslashes, NUL
   bytes, before the path is ever used to key storage.
3. per-file size cap.
4. deploy-behavior-changing filenames (``vercel.json``, ``_middleware.*``,
   ``api/*``, ``package.json``, ...) — denied outright even if their
   extension would otherwise be allowed, because they change how Vercel
   serves/builds the deployment rather than being static content.
5. extension allowlist (deny by default).
6. content-sniff agreement — images are decoded with Pillow (spoofed
   non-image bytes fail to decode), and known executable magic bytes
   (ELF, PE/MZ) are rejected regardless of the claimed extension.
7. type-specific handling: images are re-encoded via
   ``process_bundle_image()`` (fidelity-preserving, NOT
   ``image_processing.process_upload()`` — see that function's docstring),
   SVGs are re-serialized via ``svg_sanitize.sanitize_svg()`` in
   bundle-relative mode, everything else in the allowlist (CSS, JS, HTML,
   fonts) is stored byte-for-byte: there is no re-encoding equivalent for
   those types, and scripts ship verbatim in this flow by deliberate
   choice — stripping <script> would break real seller analytics/chat
   widgets and contradict "deploy as-is". Each bundle deploys to its own
   isolated Vercel project/subdomain (see apps/editor/models.py's
   SiteBundle docstring), so origin isolation is the mitigation for
   admitting scripts, not content sanitization.
8. whole-bundle invariants after every file is validated: exactly one
   top-level ``index.html``, no duplicate/case-colliding paths.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from .image_processing import ALLOWED_FORMATS, JPEG_QUALITY, MAX_UPLOAD_BYTES, ImageProcessingError
from .svg_sanitize import SvgSanitizationError, sanitize_svg

# Client-confirmed bundle caps: 100 files, 25 MB total, 8 MB per file.
MAX_BUNDLE_FILES = 100
MAX_BUNDLE_TOTAL_BYTES = 25 * 1024 * 1024
MAX_BUNDLE_FILE_BYTES = 8 * 1024 * 1024

# Extension -> Pillow format name, source format is preserved (never forced
# to JPEG — see process_bundle_image()).
IMAGE_EXTENSIONS = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}
SVG_EXTENSION = "svg"

# Extension -> content-type, stored byte-for-byte once validated. No
# re-encoding equivalent exists for these types, and scripts are admitted
# verbatim by explicit design decision (origin isolation is the mitigation,
# not content sanitization).
VERBATIM_EXTENSIONS = {
    "html": "text/html",
    "htm": "text/html",
    "css": "text/css",
    "js": "application/javascript",
    "mjs": "application/javascript",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf": "font/ttf",
    "otf": "font/otf",
    "eot": "application/vnd.ms-fontobject",
}

ALLOWED_EXTENSIONS = set(IMAGE_EXTENSIONS) | {SVG_EXTENSION} | set(VERBATIM_EXTENSIONS)

ENTRYPOINT_PATH = "index.html"

# Filenames that change deployment/build/routing behavior on Vercel rather
# than being static content — denied outright regardless of extension.
_DENIED_BASENAMES = {"vercel.json", "package.json", ".htaccess", "dockerfile"}
_DENIED_BASENAME_PREFIXES = ("_middleware.", "middleware.")
_DENIED_PATH_PREFIXES = ("api/",)

# Magic-byte signatures for common executable formats. Checked against
# every non-image file regardless of its claimed extension (an ELF binary
# named "evil.css" must not be admitted just because ".css" is allowlisted
# and stored verbatim with no other content inspection).
_EXECUTABLE_MAGIC_BYTES = (
    b"\x7fELF",  # ELF (Linux/Unix executables, shared objects)
    b"MZ",  # PE/COFF (Windows executables, DLLs)
    b"\xfe\xed\xfa\xce",  # Mach-O 32-bit
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit, little-endian
    b"\xca\xfe\xba\xbe",  # Mach-O fat binary / Java class (both rejected as non-web content)
)


class BundleValidationError(ValueError):
    """Raised for any rejected file or whole-bundle invariant violation.

    ``code`` is a stable machine-readable reason (e.g. "invalid_path",
    "type_mismatch") — the future upload endpoint (PR3+) maps it straight
    to a 400 response body, matching the ``{"error": ...}`` shape already
    used by WizardImageUploadView.
    """

    def __init__(self, code: str, message: str = "", candidates: list[str] | None = None) -> None:
        self.code = code
        self.candidates = candidates
        super().__init__(message or code)


class ImageDecompressionBombError(ImageProcessingError):
    """A structurally valid image whose pixel dimensions are an adversarial
    decompression-bomb shape (tiny compressed bytes, huge decoded pixel
    count) — distinguished from ImageProcessingError's other "not a valid
    image at all" cases so callers can map it to its own error code."""


@dataclass(frozen=True)
class BundleFile:
    """One file as provided by the caller, before any validation."""

    path: str
    data: bytes


@dataclass(frozen=True)
class ValidatedAsset:
    """One file after validation — ``path`` is normalized, ``data`` is the
    bytes to store (re-encoded for images/SVGs, verbatim otherwise)."""

    path: str
    data: bytes
    content_type: str


def process_bundle_image(data: bytes) -> tuple[bytes, str]:
    """Validate an uploaded bundle image and re-encode it in its OWN source
    format, alpha preserved, at its original dimensions.

    Reuses image_processing.py's Pillow open->verify->reopen->load guard
    chain and MAX_UPLOAD_BYTES cap (same doctrine: never store or serve an
    upload verbatim), but deliberately does NOT call process_upload()
    directly — that function forces JPEG re-encoding at MAX_DIMENSION=1600,
    which would flatten a transparent PNG onto black and downscale hero
    art, destroying the exact fidelity this "deploy as-is" flow exists to
    preserve. No GIF support (consistent with image_processing.py's
    ALLOWED_FORMATS — animated GIF is out of scope for v1).

    Returns (encoded_bytes, content_type).
    Raises ImageDecompressionBombError for an adversarial pixel-count shape,
    ImageProcessingError for anything else that isn't a safe, real image.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageProcessingError("image too large")

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()  # cheap structural check; re-open below to actually decode
        image = Image.open(io.BytesIO(data))
        image.load()  # forces full decode now, inside our size/format guards
    except Image.DecompressionBombError as exc:
        raise ImageDecompressionBombError(
            "image exceeds the maximum safe decompressed pixel count"
        ) from exc
    except Exception:
        # Pillow's per-format decoders raise a genuinely open-ended set of
        # exception types on malformed/truncated input beyond
        # UnidentifiedImageError/OSError (struct.error, zlib.error,
        # ValueError, SyntaxError, EOFError — a documented Pillow
        # robustness gap). This is an untrusted-upload decode boundary
        # inside a bundle of up to MAX_BUNDLE_FILES files: any decode
        # failure must become a clean per-file BundleValidationError, not
        # an unhandled exception that takes down the whole bundle's
        # validation with a 500.
        raise ImageProcessingError("not a valid image") from None

    if image.format not in ALLOWED_FORMATS:
        raise ImageProcessingError(f"unsupported image format: {image.format}")

    if image.width * image.height == 0:
        raise ImageProcessingError("empty image")

    buffer = io.BytesIO()
    save_kwargs = {"quality": JPEG_QUALITY, "optimize": True} if image.format == "JPEG" else {}
    image.save(buffer, format=image.format, **save_kwargs)
    return buffer.getvalue(), f"image/{image.format.lower()}"


def _normalize_path(raw_path: str) -> str:
    """Return a normalized POSIX-relative path, or raise
    BundleValidationError(code="invalid_path") for anything that isn't a
    well-behaved single-tree relative path: absolute paths, backslashes,
    NUL bytes, and any ".." segment (checked per-segment, not just the net
    effect after normalization, so "assets/../../etc/passwd" is caught the
    same way "../../etc/passwd" is)."""
    if not raw_path or "\x00" in raw_path or "\\" in raw_path:
        raise BundleValidationError("invalid_path", f"unsafe path: {raw_path!r}")
    if raw_path.startswith("/"):
        raise BundleValidationError("invalid_path", f"absolute path not allowed: {raw_path!r}")

    normalized_segments: list[str] = []
    for segment in raw_path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise BundleValidationError("invalid_path", f"path traversal not allowed: {raw_path!r}")
        normalized_segments.append(segment)

    if not normalized_segments:
        raise BundleValidationError("invalid_path", f"empty path: {raw_path!r}")
    return "/".join(normalized_segments)


def _extension(path: str) -> str:
    basename = path.rsplit("/", 1)[-1]
    if "." not in basename:
        return ""
    return basename.rsplit(".", 1)[-1].lower()


def _reject_if_deploy_behavior_file(path: str) -> None:
    basename = path.rsplit("/", 1)[-1].lower()
    if basename in _DENIED_BASENAMES:
        raise BundleValidationError("disallowed_file", f"{path} would change deployment behavior")
    if basename.startswith(_DENIED_BASENAME_PREFIXES):
        raise BundleValidationError("disallowed_file", f"{path} would change deployment behavior")
    lowered_path = path.lower()
    if lowered_path == "api" or lowered_path.startswith(_DENIED_PATH_PREFIXES):
        raise BundleValidationError("disallowed_file", f"{path} would change deployment behavior")


def _reject_if_executable_bytes(path: str, data: bytes) -> None:
    if data.startswith(_EXECUTABLE_MAGIC_BYTES):
        raise BundleValidationError("type_mismatch", f"{path}: executable content detected")


def _validate_file_content(path: str, extension: str, data: bytes) -> tuple[bytes, str]:
    if extension in IMAGE_EXTENSIONS:
        try:
            return process_bundle_image(data)
        except ImageDecompressionBombError as exc:
            raise BundleValidationError("invalid_image", str(exc)) from exc
        except ImageProcessingError as exc:
            raise BundleValidationError("type_mismatch", str(exc)) from exc

    if extension == SVG_EXTENSION:
        try:
            cleaned = sanitize_svg(data, asset_url_prefix="")
        except SvgSanitizationError as exc:
            raise BundleValidationError("invalid_svg", str(exc)) from exc
        return cleaned, "image/svg+xml"

    if extension in VERBATIM_EXTENSIONS:
        _reject_if_executable_bytes(path, data)
        return data, VERBATIM_EXTENSIONS[extension]

    raise BundleValidationError("disallowed_file", f"{path}: extension not allowed")


def validate_bundle(files: list[BundleFile]) -> list[ValidatedAsset]:
    """Validate an entire uploaded bundle and return its stored-ready assets.

    Raises BundleValidationError on the first violation found; nothing is
    ever partially written by this function (it is pure — callers persist
    the returned list themselves, once validation succeeds in full).
    """
    if not files:
        raise BundleValidationError("missing_entrypoint", "bundle is empty")

    if len(files) > MAX_BUNDLE_FILES:
        raise BundleValidationError("too_large", f"bundle exceeds the {MAX_BUNDLE_FILES}-file cap")
    if sum(len(f.data) for f in files) > MAX_BUNDLE_TOTAL_BYTES:
        raise BundleValidationError("too_large", "bundle exceeds the total size cap")

    validated: list[ValidatedAsset] = []
    seen_casefold: set[str] = set()

    for bundle_file in files:
        path = _normalize_path(bundle_file.path)

        casefold_path = path.casefold()
        if casefold_path in seen_casefold:
            raise BundleValidationError("duplicate_path", f"duplicate path: {path!r}")
        seen_casefold.add(casefold_path)

        if len(bundle_file.data) > MAX_BUNDLE_FILE_BYTES:
            raise BundleValidationError("too_large", f"{path} exceeds the per-file size cap")

        _reject_if_deploy_behavior_file(path)

        extension = _extension(path)
        data, content_type = _validate_file_content(path, extension, bundle_file.data)
        validated.append(ValidatedAsset(path=path, data=data, content_type=content_type))

    if not any(_extension(asset.path) in ("html", "htm") for asset in validated):
        raise BundleValidationError("missing_entrypoint", "bundle has no HTML file")

    return validated


def resolve_entrypoint(validated: list[ValidatedAsset], requested: str | None) -> str:
    """Resolve which validated asset serves the bundle's "/" — kept out of
    validate_bundle() on purpose (see design: entrypoint resolution stays
    out of validate_bundle) so that function stays pure/single-purpose and
    this one owns the request-shaped "which HTML file did the seller pick"
    concern.

    - If `requested` is given, it MUST be one of `validated`'s HTML/HTM
      paths, or this raises BundleValidationError("invalid_entrypoint").
    - Otherwise, a top-level "index.html" is auto-selected if present.
    - Otherwise, raises BundleValidationError("entrypoint_required") with
      `.candidates` set to the sorted list of the bundle's HTML/HTM paths —
      the seller must pick one explicitly (a nested index.html, e.g.
      "pages/index.html", does NOT count as "top-level" and is only offered
      as a candidate, never auto-selected).
    """
    html_paths = sorted(
        asset.path for asset in validated if _extension(asset.path) in ("html", "htm")
    )

    if requested:
        if requested not in html_paths:
            raise BundleValidationError(
                "invalid_entrypoint", f"not a validated HTML asset: {requested!r}"
            )
        return requested

    if ENTRYPOINT_PATH in html_paths:
        return ENTRYPOINT_PATH

    raise BundleValidationError(
        "entrypoint_required",
        "no top-level index.html — an entrypoint must be chosen",
        candidates=html_paths,
    )
