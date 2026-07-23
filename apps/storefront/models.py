import secrets

from django.conf import settings
from django.db import models

from apps.editor.models import UploadedAsset


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
    verified Stripe webhook (never from the checkout-redirect view, which
    runs before payment is confirmed)."""

    class Status(models.TextChoices):
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"

    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name="orders"
    )
    stripe_session_id = models.CharField(max_length=255, unique=True)
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

    def __str__(self):
        return f"{self.stripe_session_id} ({self.status})"

    @staticmethod
    def generate_download_token() -> str:
        return secrets.token_urlsafe(32)
