from rest_framework import serializers

from .models import Project, ProjectRevision


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "state", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRevision
        fields = ["id", "version", "state", "source", "summary", "created_at", "user"]
        read_only_fields = ["id", "version", "created_at", "user"]
