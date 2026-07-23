from django.contrib import admin

from .models import Order, PaymentGatewayConfig, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "price_cents", "is_active", "updated_at"]
    search_fields = ["name", "owner__username"]
    list_filter = ["is_active"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "gateway",
        "gateway_session_id",
        "product",
        "status",
        "amount_cents",
        "currency",
        "created_at",
    ]
    list_filter = ["status", "gateway"]
    search_fields = ["gateway_session_id", "buyer_email"]


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    # Never list/search by credentials_encrypted — it's ciphertext, not
    # meaningful to browse, and no admin view should ever decrypt it for
    # display (that would defeat the point of encrypting it at rest).
    list_display = ["owner", "gateway", "is_enabled", "updated_at"]
    list_filter = ["gateway", "is_enabled"]
    search_fields = ["owner__username"]
