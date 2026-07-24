from rest_framework import serializers

from apps.editor.palettes import PaletteValidationError, validate_palette_state

from .models import Project, ProjectRevision


class ProjectSerializer(serializers.ModelSerializer):
    def validate_state(self, value):
        try:
            validate_palette_state(value)
        except PaletteValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    class Meta:
        model = Project
        fields = ["id", "name", "state", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectRevisionSerializer(serializers.ModelSerializer):
    def validate_state(self, value):
        try:
            validate_palette_state(value)
        except PaletteValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    class Meta:
        model = ProjectRevision
        fields = ["id", "version", "state", "source", "summary", "created_at", "user"]
        read_only_fields = ["id", "version", "created_at", "user"]
