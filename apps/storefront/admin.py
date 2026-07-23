from django.contrib import admin

from .models import Order, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "price_cents", "is_active", "updated_at"]
    search_fields = ["name", "owner__username"]
    list_filter = ["is_active"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "stripe_session_id",
        "product",
        "status",
        "amount_cents",
        "currency",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["stripe_session_id", "buyer_email"]
