from rest_framework import serializers

from .file_validation import FileValidationError
from .file_validation import validate_digital_file as check_digital_file
from .models import PaymentGatewayConfig, Product
from .payments import GATEWAY_REGISTRY


class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.CharField(source="image.file.url", read_only=True, default=None)
    has_digital_file = serializers.SerializerMethodField()
    # Explicit default: DRF's BooleanField treats an absent key as False for
    # multipart/form data (HTML checkbox convention) rather than falling
    # back to the model's own default=True — verified while creating a
    # product through the multipart products.js form (no is_active field
    # sent at all) silently landed as inactive. A plain JSON POST doesn't
    # hit this since there the field is simply omitted, not form-coerced.
    is_active = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price_cents",
            "image",
            "image_url",
            "digital_file",
            "has_digital_file",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "has_digital_file", "created_at", "updated_at"]
        # Never returned in a response (even to the owner) — its raw storage
        # path/URL isn't meant to be exposed anywhere; has_digital_file is
        # the read-side signal that one exists (FEATURE.md 1.6b).
        extra_kwargs = {"digital_file": {"write_only": True}}

    def get_has_digital_file(self, obj):
        return bool(obj.digital_file)

    def validate_image(self, value):
        request = self.context.get("request")
        if value is not None and request and value.owner_id != request.user.id:
            raise serializers.ValidationError("image must be one of your own uploads")
        return value

    def validate_price_cents(self, value):
        if value <= 0:
            raise serializers.ValidationError("price must be a positive amount")
        return value

    def validate_digital_file(self, value):
        if value is None:
            return value
        data = value.read()
        value.seek(0)
        try:
            check_digital_file(data)
        except FileValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    """`credentials` is write-only: a PATCH/POST merges the given fields
    into whatever's already encrypted-and-stored, and a GET/list response
    never includes it, even to the owner who set it — `has_credentials`
    (a per-field presence map, not the values themselves) is the read-side
    signal the UI uses to show "ya configurado" vs empty."""

    credentials = serializers.DictField(write_only=True, required=False)
    has_credentials = serializers.SerializerMethodField()
    required_fields = serializers.SerializerMethodField()

    class Meta:
        model = PaymentGatewayConfig
        fields = [
            "id",
            "gateway",
            "is_enabled",
            "credentials",
            "has_credentials",
            "required_fields",
            "updated_at",
        ]
        read_only_fields = ["id", "has_credentials", "required_fields", "updated_at"]

    def get_has_credentials(self, obj):
        required_fields, _factory, _fake = GATEWAY_REGISTRY.get(obj.gateway, ([], None, None))
        stored = obj.get_credentials()
        return {field: bool(stored.get(field)) for field in required_fields}

    def get_required_fields(self, obj):
        required_fields, _factory, _fake = GATEWAY_REGISTRY.get(obj.gateway, ([], None, None))
        return required_fields

    def validate_gateway(self, value):
        if value not in GATEWAY_REGISTRY:
            raise serializers.ValidationError(f"unknown gateway: {value}")
        return value

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", {})
        instance = super().create(validated_data)
        if credentials:
            instance.set_credentials(credentials)
            instance.save(update_fields=["credentials_encrypted"])
        return instance

    def update(self, instance, validated_data):
        credentials = validated_data.pop("credentials", None)
        instance = super().update(instance, validated_data)
        if credentials is not None:
            # Merge, don't replace — a PATCH sending only a changed field
            # (e.g. just toggling is_enabled) must never wipe out
            # previously-saved credentials for the other fields.
            merged = instance.get_credentials()
            merged.update(credentials)
            instance.set_credentials(merged)
            instance.save(update_fields=["credentials_encrypted"])
        return instance
