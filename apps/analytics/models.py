import uuid

from django.db import models


class AnalyticsVisitor(models.Model):
    """A consented, pseudonymous browser identifier.

    This is deliberately separate from Django's authentication/session tables:
    an analytics cookie must never become an implicit user identity.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    consented_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["last_seen"])]

    def __str__(self):
        return str(self.pk)


class AnalyticsSession(models.Model):
    """One anonymous visit to one published template."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor = models.ForeignKey(
        AnalyticsVisitor,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    template = models.ForeignKey(
        "editor.UserTemplate",
        on_delete=models.CASCADE,
        related_name="analytics_sessions",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    entry_path = models.CharField(max_length=200, default="/")
    exit_target = models.CharField(max_length=120, blank=True)
    viewport_width = models.PositiveSmallIntegerField(null=True, blank=True)
    viewport_height = models.PositiveSmallIntegerField(null=True, blank=True)
    event_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["template", "started_at"]),
            models.Index(fields=["visitor", "started_at"]),
        ]

    def __str__(self):
        return f"{self.template_id}:{self.pk}"


class AnalyticsEvent(models.Model):
    class Kind(models.TextChoices):
        PAGEVIEW = "pageview", "Page view"
        HEARTBEAT = "heartbeat", "Heartbeat"
        CLICK = "click", "Click"
        MOVE = "move", "Pointer sample"
        PAGE_EXIT = "page_exit", "Page exit"

    session = models.ForeignKey(
        AnalyticsSession,
        on_delete=models.CASCADE,
        related_name="events",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    occurred_at = models.DateTimeField(auto_now_add=True)
    x = models.DecimalField(max_digits=6, decimal_places=5, null=True, blank=True)
    y = models.DecimalField(max_digits=6, decimal_places=5, null=True, blank=True)
    target = models.CharField(max_length=120, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    viewport_width = models.PositiveSmallIntegerField(null=True, blank=True)
    viewport_height = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["session", "kind", "occurred_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(x__isnull=True) | models.Q(x__gte=0, x__lte=1),
                name="analytics_event_x_between_zero_and_one",
            ),
            models.CheckConstraint(
                condition=models.Q(y__isnull=True) | models.Q(y__gte=0, y__lte=1),
                name="analytics_event_y_between_zero_and_one",
            ),
        ]

    def __str__(self):
        return f"{self.kind}:{self.session_id}"
