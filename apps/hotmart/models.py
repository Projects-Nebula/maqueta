"""Hotmart integration models (see openspec design:
hotmart-developer-credentials-pivot).

Per-seller Developer Credentials (`client_id`/`client_secret`) and access
tokens are encrypted at rest with the EXISTING apps/storefront/crypto.py
(Fernet over SHA256(SECRET_KEY)) — no new crypto is introduced here, same
as PaymentGatewayConfig.credentials_encrypted.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.storefront.crypto import CredentialDecryptionError, decrypt_value, encrypt_value

# Skew applied when checking token expiry: treat a token as expired slightly
# before its real expiry so a request in flight doesn't race the deadline.
_EXPIRY_SKEW = timedelta(seconds=60)


class HotmartConnection(models.Model):
    """One Hotmart account per maqueta user (client-confirmed 1-to-1,
    enforced here via OneToOneField rather than an application-level
    check)."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hotmart_connection"
    )
    hotmart_account_id = models.CharField(max_length=128, blank=True)
    credentials_encrypted = models.TextField(blank=True)
    access_token_encrypted = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.owner_id}:hotmart"

    def set_credentials(self, data: dict) -> None:
        """Stores `client_id`/`client_secret` as a single Fernet-encrypted
        JSON blob (mirrors PaymentGatewayConfig.set_credentials)."""
        self.credentials_encrypted = encrypt_value(json.dumps(data))

    def get_credentials(self) -> dict:
        if not self.credentials_encrypted:
            return {}
        try:
            return json.loads(decrypt_value(self.credentials_encrypted))
        except CredentialDecryptionError:
            return {}

    def has_credentials(self) -> bool:
        creds = self.get_credentials()
        return bool(creds.get("client_id")) and bool(creds.get("client_secret"))

    def set_tokens(self, *, access: str, expires_in: int) -> None:
        """`client_credentials` grants never return a refresh token — only
        the access token and its expiry are stored (see design's "expiry
        re-exchanges" decision)."""
        self.access_token_encrypted = encrypt_value(access)
        self.expires_at = timezone.now() + timedelta(seconds=expires_in)

    def get_access_token(self) -> str:
        if not self.access_token_encrypted:
            return ""
        try:
            return decrypt_value(self.access_token_encrypted)
        except CredentialDecryptionError:
            return ""

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        return timezone.now() >= (self.expires_at - _EXPIRY_SKEW)


class HotmartProductLink(models.Model):
    """Metadata-only 1-to-1 link between a Hotmart product and a landing
    (UserTemplate). No price/checkout logic is duplicated here — see design
    doc's "no local product mirror" decision."""

    class Status(models.TextChoices):
        ACTIVE = "active"
        UPSTREAM_MISSING = "upstream_missing"

    connection = models.ForeignKey(
        HotmartConnection, on_delete=models.CASCADE, related_name="product_links"
    )
    user_template = models.OneToOneField(
        "editor.UserTemplate", on_delete=models.CASCADE, related_name="hotmart_link"
    )
    hotmart_product_id = models.CharField(max_length=64)
    product_name = models.CharField(max_length=255, blank=True)
    checkout_url = models.URLField(blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("connection", "hotmart_product_id")]

    def __str__(self):
        return f"{self.hotmart_product_id} -> {self.user_template_id} ({self.status})"

    def mark_missing(self) -> None:
        self.status = self.Status.UPSTREAM_MISSING
        self.save(update_fields=["status", "updated_at"])
