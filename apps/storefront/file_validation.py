"""Validation for a Product's downloadable digital_file upload.

Deliberately parallel to apps/editor/image_processing.py, not a reuse of
it: that module re-encodes images from scratch (would corrupt a PDF/zip).
This module never touches the bytes beyond reading a small header to
verify the real file type — the upload is stored as-is once validated.
"""

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB — bigger than images, tune if needed.

# (declared content-type, magic-byte signature) — never trust the
# client-supplied Content-Type or filename extension alone.
ALLOWED_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "application/zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}


class FileValidationError(ValueError):
    """Raised when an uploaded digital file isn't a safe, real file of an
    allowed type."""


def validate_digital_file(data: bytes) -> str:
    """Validate a digital product upload. Returns the detected content
    type on success. Raises FileValidationError otherwise."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileValidationError("file too large")
    if not data:
        raise FileValidationError("empty file")

    for content_type, signatures in ALLOWED_SIGNATURES.items():
        if any(data.startswith(sig) for sig in signatures):
            return content_type

    raise FileValidationError("unsupported file type")
