from django.conf import settings
from django.db import models

from .rendering import thumbnail_srcdoc


class Template(models.Model):
    """A starting page template selectable from the gallery. `state` holds the
    full editor document JSON; a null state means "use the editor's built-in
    default page" (the landing example)."""

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    accent = models.CharField(max_length=9, blank=True)  # hex color, e.g. #5b5ce2
    state = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def thumbnail_srcdoc(self):
        return thumbnail_srcdoc(self.state)


class UserTemplate(models.Model):
    """A template a user saved from their own editor state."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_templates"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    accent = models.CharField(max_length=9, blank=True)
    state = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    def thumbnail_srcdoc(self):
        return thumbnail_srcdoc(self.state)


class UserTemplateRevision(models.Model):
    """Snapshot of a UserTemplate's state before an update overwrote it."""

    user_template = models.ForeignKey(
        UserTemplate, on_delete=models.CASCADE, related_name="revisions"
    )
    version = models.PositiveIntegerField()
    state = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        unique_together = ("user_template", "version")

    def __str__(self):
        return f"{self.user_template_id} v{self.version}"
