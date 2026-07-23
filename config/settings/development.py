"""Local development settings."""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]

# Plain static storage in dev: no collectstatic/manifest needed to serve pages.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Content-Security-Policy that still allows the editor iframe (srcdoc) to run
# its own inline styles/scripts while blocking remote code.
CSP_HEADER = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com "
    "https://player.vimeo.com; "
    "connect-src 'self'"
)
