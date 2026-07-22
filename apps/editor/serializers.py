from rest_framework import serializers

from .models import UserTemplate, UserTemplateRevision


class UserTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTemplate
        fields = ["id", "name", "description", "accent", "state", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserTemplateRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTemplateRevision
        fields = ["id", "version", "state", "created_at"]
        read_only_fields = fields
