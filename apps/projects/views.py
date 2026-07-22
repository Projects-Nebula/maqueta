"""Project CRUD + revisions. Every query is scoped to the owner (no IDOR)."""

from django.db.models import Max
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Project
from .serializers import ProjectRevisionSerializer, ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Scoping here is the IDOR guard: a user can never see others' rows,
        # so detail routes 404 instead of leaking existence.
        return Project.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get", "post"])
    def revisions(self, request, pk=None):
        project = self.get_object()  # already owner-scoped

        if request.method == "GET":
            serializer = ProjectRevisionSerializer(project.revisions.all(), many=True)
            return Response(serializer.data)

        serializer = ProjectRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_version = (project.revisions.aggregate(top=Max("version"))["top"] or 0) + 1
        revision = serializer.save(project=project, version=next_version, user=request.user)
        return Response(ProjectRevisionSerializer(revision).data, status=status.HTTP_201_CREATED)
