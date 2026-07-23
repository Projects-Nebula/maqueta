from rest_framework import serializers

from .file_validation import FileValidationError
from .file_validation import validate_digital_file as check_digital_file
from .models import Product


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
