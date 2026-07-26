from django.utils.text import slugify
from rest_framework import serializers

from .models import AuditEvent, UploadedAsset, UserPalette, UserTemplate, UserTemplateRevision
from .palettes import (
    PaletteValidationError,
    validate_palette_metadata,
    validate_palette_state,
    validate_palette_variables,
)


def _unique_palette_slug(owner, name: str) -> str:
    base = f"custom-{slugify(name) or 'palette'}"[:64].rstrip("-") or "custom-palette"
    slug = base
    suffix = 2
    while owner.user_palettes.filter(slug=slug).exists():
        suffix_text = f"-{suffix}"
        slug = f"{base[: 64 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return slug


class UserPaletteSerializer(serializers.ModelSerializer):
    def validate_name(self, value):
        try:
            return validate_palette_metadata({"id": "custom", "name": value, "source": "custom"})[
                "name"
            ]
        except PaletteValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_variables(self, value):
        try:
            return validate_palette_variables(value, require_all=True)
        except PaletteValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def create(self, validated_data):
        owner = validated_data.pop("owner", None)
        if owner is None:
            raise serializers.ValidationError("owner is required")
        validated_data["slug"] = _unique_palette_slug(owner, validated_data["name"])
        return UserPalette.objects.create(owner=owner, **validated_data)

    class Meta:
        model = UserPalette
        fields = ["id", "slug", "name", "variables", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class UserTemplateSerializer(serializers.ModelSerializer):
    def validate_state(self, value):
        try:
            validate_palette_state(value)
        except PaletteValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    class Meta:
        model = UserTemplate
        fields = [
            "id",
            "name",
            "description",
            "accent",
            "state",
            "is_published",
            "public_slug",
            "created_at",
            "updated_at",
        ]
        # is_published/public_slug are set only via the publish/unpublish
        # actions (apps/editor/views.py), never a raw PATCH — read-only here.
        read_only_fields = ["id", "is_published", "public_slug", "created_at", "updated_at"]


class UserTemplateRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTemplateRevision
        fields = ["id", "version", "state", "created_at"]
        read_only_fields = fields


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ["id", "action", "target_type", "target_id", "metadata", "created_at"]
        read_only_fields = fields


class UploadedAssetSerializer(serializers.ModelSerializer):
    # Relative (same-origin app, see project.md) — matches what
    # sanitize.check_url_value already accepts for any other src/href.
    url = serializers.CharField(source="file.url", read_only=True)

    class Meta:
        model = UploadedAsset
        fields = ["id", "url", "width", "height", "created_at"]
        read_only_fields = fields
