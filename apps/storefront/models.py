import json
import secrets

from django.conf import settings
from django.db import models

from apps.editor.models import UploadedAsset

from .crypto import CredentialDecryptionError, decrypt_value, encrypt_value
from .payments import GATEWAY_CHOICES


class Product(models.Model):
    """Something an owner can sell on a published page (FEATURE.md). Price
    is always an integer minor-unit amount (price_cents) — never a float,
    same reasoning Stripe itself uses. digital_file is optional: set it for
    a downloadable (PDF/zip), leave it unset for a plain "buy this" with no
    file delivery."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price_cents = models.PositiveIntegerField()
    image = models.ForeignKey(UploadedAsset, null=True, blank=True, on_delete=models.SET_NULL)
    digital_file = models.FileField(upload_to="product-files/%Y/%m/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Order(models.Model):
    """The permanent record of a completed (or attempted) purchase — the
    direct answer to "what did we sell and to whom". Created ONLY from a
    verified webhook for real gateways (never from the checkout-redirect
    view, which runs before payment is confirmed) — the fake-provider dev
    path is a deliberate, narrow exception (see
    apps/storefront/views.py's _record_order_for_session)."""

    class Status(models.TextChoices):
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"

    class Gateway(models.TextChoices):
        STRIPE = "stripe"
        MERCADOPAGO = "mercadopago"
        PAYPAL = "paypal"
        BRAINTREE = "braintree"
        WOMPI = "wompi"
        PAYU = "payu"
        EPAYCO = "epayco"
        BOLD = "bold"
        # Not a real payment gateway — the seller has none enabled at all.
        # CheckoutView delivers the product directly and records a $0 Order
        # (never silently un-tracked) instead of 404ing.
        NONE = "none"

    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name="orders"
    )
    gateway = models.CharField(max_length=16, choices=Gateway.choices, default=Gateway.STRIPE)
    gateway_session_id = models.CharField(max_length=255)
    buyer_email = models.EmailField(blank=True)
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=8)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    # Only meaningful when product.digital_file is set — a capability
    # token minted at Order-creation time (i.e. only once payment is
    # confirmed), never earlier.
    download_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    max_downloads = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Two different gateways could theoretically mint colliding session
        # id strings — uniqueness is scoped per gateway, not global.
        unique_together = [("gateway", "gateway_session_id")]

    def __str__(self):
        return f"{self.gateway}:{self.gateway_session_id} ({self.status})"

    @staticmethod
    def generate_download_token() -> str:
        return secrets.token_urlsafe(32)


class PaymentGatewayConfig(models.Model):
    """One row per gateway, owner-configured via /config. Credentials are
    stored as a single Fernet-encrypted JSON blob (apps/storefront/crypto.py)
    — never in plaintext, never returned by any API response (see
    PaymentGatewayConfigSerializer). `is_enabled` is the actual on/off
    switch a buyer sees: a disabled gateway's checkout button does not
    render at all, regardless of whether credentials exist for it.

    Owner-scoped, same as Product: each seller configures their OWN gateway
    credentials (this is a multi-tenant editor — /productos/ is already
    owner-scoped, so a shared/global credential set would be wrong). A
    checkout looks up the config by the PRODUCT'S owner, never the buyer
    (who may be anonymous or a different logged-in user entirely)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_gateway_configs"
    )
    gateway = models.CharField(max_length=16, choices=[(g, g) for g in GATEWAY_CHOICES])
    is_enabled = models.BooleanField(default=False)
    credentials_encrypted = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["gateway"]
        unique_together = [("owner", "gateway")]

    def __str__(self):
        return f"{self.owner_id}:{self.gateway} ({'enabled' if self.is_enabled else 'disabled'})"

    def get_credentials(self) -> dict:
        if not self.credentials_encrypted:
            return {}
        try:
            return json.loads(decrypt_value(self.credentials_encrypted))
        except CredentialDecryptionError:
            return {}

    def set_credentials(self, data: dict) -> None:
        self.credentials_encrypted = encrypt_value(json.dumps(data))

    def has_complete_credentials(self, required_fields: list[str]) -> bool:
        creds = self.get_credentials()
        return all(creds.get(f) for f in required_fields)
