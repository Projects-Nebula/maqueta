"""Server-side image processing for wizard uploads.

Nothing here trusts the client: a spoofed extension or an oversized/decompression-
bomb-shaped file must fail here, before anything touches disk or another
request's resources. Pillow re-encodes every upload from scratch (never
just copies bytes through), which also strips EXIF/metadata.
"""

import io

from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB — rejected before Pillow ever opens it.
MAX_DIMENSION = 1600  # long edge, px — downscaled if larger.
JPEG_QUALITY = 85
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageProcessingError(ValueError):
    """Raised when an upload isn't a usable image."""


def process_upload(data: bytes) -> tuple[bytes, str, int, int]:
    """Validate, downscale, and re-encode an uploaded image.

    Returns (encoded_bytes, content_type, width, height). Raises
    ImageProcessingError for anything that isn't a safe, real image.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageProcessingError("image too large")

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()  # cheap structural check; re-open below to actually decode
        image = Image.open(io.BytesIO(data))
        image.load()  # forces full decode now, inside our size/format guards
    except (UnidentifiedImageError, OSError):
        raise ImageProcessingError("not a valid image") from None

    if image.format not in ALLOWED_FORMATS:
        raise ImageProcessingError(f"unsupported image format: {image.format}")

    if image.width * image.height == 0:
        raise ImageProcessingError("empty image")

    if max(image.width, image.height) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), "image/jpeg", image.width, image.height
