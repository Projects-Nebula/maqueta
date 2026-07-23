"""Encryption at rest for payment gateway credentials (PaymentGatewayConfig).

Fernet requires a 32-byte urlsafe-base64 key; Django's own SECRET_KEY is an
arbitrary-length string, so it's hashed down to exactly 32 bytes first. This
means rotating DJANGO_SECRET_KEY without a migration plan makes every
already-stored credential unreadable — same tradeoff as any secret-derived
encryption key, documented here rather than discovered the hard way.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredentialDecryptionError(Exception):
    """Raised when a stored credential can't be decrypted (wrong/rotated key)."""


def _fernet() -> Fernet:
    key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise CredentialDecryptionError("stored credential could not be decrypted") from exc
