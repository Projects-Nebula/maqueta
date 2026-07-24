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
    is_published = models.BooleanField(default=False)
    # Stable once set — never regenerated on unpublish/republish (see
    # FEATURE.md 1.1). Random suffix avoids collisions across users with
    # the same template name; not meant to be secret, just unique.
    public_slug = models.SlugField(max_length=140, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    def thumbnail_srcdoc(self):
        return thumbnail_srcdoc(self.state)

    def publish(self):
        if not self.public_slug:
            import secrets

            from django.utils.text import slugify

            base = slugify(self.name)[:100] or "template"
            self.public_slug = f"{base}-{secrets.token_hex(3)}"
        self.is_published = True
        self.save(update_fields=["is_published", "public_slug", "updated_at"])

    def unpublish(self):
        self.is_published = False
        self.save(update_fields=["is_published", "updated_at"])


class UserPalette(models.Model):
    """A reusable four-role palette owned by one user.

    The palette is a catalog entry, not a second document styling source:
    applying it copies ``variables`` into a template's ``styles.variables``.
    ``slug`` remains stable so saved templates can keep safe provenance
    metadata even if the display name changes later.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_palettes"
    )
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=80)
    variables = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "slug"], name="editor_userpalette_owner_slug_unique"
            )
        ]

    def __str__(self):
        return self.name


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


class UploadedAsset(models.Model):
    """An image a user uploaded for the wizard, already resized/re-encoded
    server-side (see apps.editor.image_processing) — never the raw upload."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="uploaded_assets"
    )
    file = models.ImageField(upload_to="wizard-uploads/%Y/%m/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.file.name
