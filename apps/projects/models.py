import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=200)
    state = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ProjectRevision(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual"
        AI = "ai"
        IMPORT = "import"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="revisions")
    version = models.PositiveIntegerField()
    state = models.JSONField(default=dict)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    summary = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-version"]
        unique_together = ("project", "version")

    def __str__(self):
        return f"{self.project_id} v{self.version}"
