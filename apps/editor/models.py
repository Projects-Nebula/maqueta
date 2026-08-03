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


class AuditEvent(models.Model):
    """A record of a server-mediated mutating action, for traceability —
    e.g. which AI instruction produced a given UserTemplateRevision. Only
    ever written server-side after the action already succeeded; adds no new
    trust boundary. Purely client-side actions (e.g. applying a palette
    preset, which never round-trips through the server) are not logged here
    — logging them would mean adding a server endpoint just to log, which
    isn't worth it without another reason to have one."""

    class Action(models.TextChoices):
        AI_TRANSFORM = "ai_transform"
        AI_WIZARD_GENERATE = "ai_wizard_generate"
        TEMPLATE_CREATE = "template_create"
        TEMPLATE_SAVE = "template_save"

    # Grows on every AI call, unlike UserTemplateRevision — cap per owner the
    # same way (record() prunes right after inserting) so metadata (AI
    # instruction text) doesn't accumulate forever with no retention path,
    # matching the precedent every other retained-user-data model here sets.
    RETENTION_LIMIT = 100

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="audit_events"
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    target_type = models.CharField(max_length=32, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.owner_id}:{self.action}@{self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def record(cls, *, owner, action, target_type="", target_id=None, metadata=None):
        """Create an event and prune this owner's events to RETENTION_LIMIT."""
        event = cls.objects.create(
            owner=owner,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )
        keep_ids = cls.objects.filter(owner=owner).values_list("pk", flat=True)[
            : cls.RETENTION_LIMIT
        ]
        cls.objects.filter(owner=owner).exclude(pk__in=list(keep_ids)).delete()
        return event


class SiteBundle(models.Model):
    """An owner-scoped upload of a finished static site (HTML + assets),
    validated once by apps.editor.asset_validation.validate_bundle() and
    then forked into two flows: deploy-as-is
    (apps.vercel.services.deploy_bundle, PR3 of this change) or
    convert-to-editable (site-bundle-import's node converter, PR3/4 of that
    change — not built here). This model and BundleAsset are path-agnostic
    on purpose: they carry no opinion about which flow consumes them, so
    the flows fork after ingestion instead of each maintaining its own
    upload/validation copy."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="site_bundles"
    )
    name = models.CharField(max_length=120)
    # Stable once set, same pattern as UserTemplate.public_slug — used as
    # the Vercel project name (mq-{public_slug}). One Vercel project per
    # SiteBundle is the origin-isolation boundary a malicious script in a
    # deployed bundle can't cross (see apps/vercel/client.py). Set by the
    # deploy flow (PR3), not at ingestion time.
    public_slug = models.SlugField(max_length=140, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class BundleAsset(models.Model):
    """One validated file within a SiteBundle. ``path`` is the bundle-
    relative lookup key (e.g. "assets/logo.png", "index.html") used to
    resolve references from the HTML — never a filesystem path (see
    apps.editor.asset_validation's path-hardening doctrine). Exactly one
    asset per bundle has ``path == "index.html"``, enforced by
    ``validate_bundle()`` before any BundleAsset is ever created, not by a
    DB constraint here."""

    bundle = models.ForeignKey(SiteBundle, on_delete=models.CASCADE, related_name="assets")
    path = models.CharField(max_length=255)
    file = models.FileField(upload_to="site-bundles/%Y/%m/")
    content_type = models.CharField(max_length=100)
    byte_size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["path"]
        constraints = [
            models.UniqueConstraint(
                fields=["bundle", "path"], name="editor_bundleasset_bundle_path_unique"
            )
        ]

    def __str__(self):
        return f"{self.bundle_id}:{self.path}"


class UploadedAsset(models.Model):
    """An image a user uploaded for the wizard, already resized/re-encoded
    server-side (see apps.editor.image_processing) — never the raw upload."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="uploaded_assets"
    )
    file = models.ImageField(upload_to="wizard-uploads/%Y/%m/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    # One-pixel average color, e.g. "#a1b2c3" — a cheap loading placeholder
    # for the asset pickers (see image_processing._dominant_color_hex).
    placeholder_color = models.CharField(max_length=7, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.file.name
