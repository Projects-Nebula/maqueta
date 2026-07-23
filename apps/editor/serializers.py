from rest_framework import serializers

from .models import UploadedAsset, UserTemplate, UserTemplateRevision


class UserTemplateSerializer(serializers.ModelSerializer):
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


class UploadedAssetSerializer(serializers.ModelSerializer):
    # Relative (same-origin app, see project.md) — matches what
    # sanitize.check_url_value already accepts for any other src/href.
    url = serializers.CharField(source="file.url", read_only=True)

    class Meta:
        model = UploadedAsset
        fields = ["id", "url", "width", "height", "created_at"]
        read_only_fields = fields
