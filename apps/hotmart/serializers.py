"""Token-free serializers for the Hotmart API surface (see openspec design:
hotmart-developer-credentials-pivot, "Security Approach" — no
credential/token/ciphertext ever appears in a response).
"""

from __future__ import annotations

from rest_framework import serializers

from apps.editor.models import UserTemplate

from .models import HotmartConnection, HotmartProductLink


class HotmartCredentialsSerializer(serializers.Serializer):
    """Write-only input for POST /api/hotmart/credentials/. Both fields
    are optional (blank means "keep the existing stored value" — spec:
    "Rotating one credential") — CredentialsView resolves the blank-keeps-
    existing merge, this serializer only validates shape/presence of
    fields."""

    client_id = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    client_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default=""
    )


class HotmartConnectionSerializer(serializers.ModelSerializer):
    """Read-only status serializer: `connected` is always True for any row
    that exists (a disconnect deletes the row entirely), so the client
    only ever needs to check whether the request for this resource 404s
    or succeeds — this shape matches the spec's "No Token Exposure"
    requirement (no token, no ciphertext, ever)."""

    connected = serializers.SerializerMethodField()

    class Meta:
        model = HotmartConnection
        fields = ["connected", "hotmart_account_id", "expires_at", "connected_at"]
        read_only_fields = fields

    def get_connected(self, obj):
        return True


class HotmartProductLinkSerializer(serializers.ModelSerializer):
    """Metadata-only link between a Hotmart product and a landing (design:
    "no local product mirror" — this row stores only display metadata, no
    price/checkout logic)."""

    user_template = serializers.PrimaryKeyRelatedField(queryset=UserTemplate.objects.all())

    class Meta:
        model = HotmartProductLink
        fields = [
            "id",
            "user_template",
            "hotmart_product_id",
            "product_name",
            "checkout_url",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_user_template(self, value):
        request = self.context.get("request")
        if request is not None and value.owner_id != request.user.id:
            raise serializers.ValidationError("user_template must be one of your own templates")
        return value

    def validate_checkout_url(self, value):
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("checkout_url must use https")
        return value

    def validate(self, attrs):
        connection = self.context["connection"]
        instance_pk = self.instance.pk if self.instance else None

        user_template = attrs.get("user_template")
        if user_template is not None:
            clash = HotmartProductLink.objects.filter(user_template=user_template).exclude(
                pk=instance_pk
            )
            if clash.exists():
                raise serializers.ValidationError(
                    {"user_template": "this landing is already linked to a product"}
                )

        hotmart_product_id = attrs.get("hotmart_product_id")
        if hotmart_product_id:
            clash = HotmartProductLink.objects.filter(
                connection=connection, hotmart_product_id=hotmart_product_id
            ).exclude(pk=instance_pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"hotmart_product_id": "this product is already linked to a landing"}
                )

        return attrs
