"""Read-only Hotmart admin views (see openspec design: hotmart-oauth-connect,
"Security Approach" — tokens are decrypted only inside services.py, never
in an admin field or list display, same rule as PaymentGatewayConfigAdmin
in apps/storefront/admin.py)."""

from django.contrib import admin

from .models import HotmartConnection, HotmartProductLink


@admin.register(HotmartConnection)
class HotmartConnectionAdmin(admin.ModelAdmin):
    # *_encrypted fields are deliberately excluded everywhere below —
    # ciphertext isn't meaningful to browse, and no admin view should ever
    # decrypt it for display (that would defeat the point of encrypting it
    # at rest).
    list_display = ["owner", "hotmart_account_id", "is_expired", "connected_at", "updated_at"]
    search_fields = ["owner__username", "hotmart_account_id"]
    readonly_fields = [
        "owner",
        "hotmart_account_id",
        "expires_at",
        "connected_at",
        "updated_at",
    ]
    exclude = ["access_token_encrypted", "refresh_token_encrypted"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HotmartProductLink)
class HotmartProductLinkAdmin(admin.ModelAdmin):
    list_display = [
        "connection",
        "hotmart_product_id",
        "product_name",
        "status",
        "updated_at",
    ]
    list_filter = ["status"]
    search_fields = [
        "hotmart_product_id",
        "product_name",
        "connection__owner__username",
    ]
    readonly_fields = [
        "connection",
        "user_template",
        "hotmart_product_id",
        "product_name",
        "checkout_url",
        "status",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
