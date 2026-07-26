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


def _dominant_color_hex(image: Image.Image) -> str:
    """A cheap loading placeholder: the image downsampled to one pixel.

    ponytail: a full blurhash decode needs a JS DCT decoder with no build
    step to vendor it into (static/editor/*.js has none); a one-pixel
    average color gets the same "don't show a blank box while it loads" UX
    with a one-line client-side background-color instead.
    """
    r, g, b = image.convert("RGB").resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


def process_upload(data: bytes) -> tuple[bytes, str, int, int, str]:
    """Validate, downscale, and re-encode an uploaded image.

    Returns (encoded_bytes, content_type, width, height, placeholder_color).
    Raises ImageProcessingError for anything that isn't a safe, real image.
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

    placeholder_color = _dominant_color_hex(image)

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), "image/jpeg", image.width, image.height, placeholder_color
