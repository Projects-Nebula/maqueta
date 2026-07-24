from django.contrib import admin

from .models import AnalyticsEvent, AnalyticsSession, AnalyticsVisitor


@admin.register(AnalyticsVisitor)
class AnalyticsVisitorAdmin(admin.ModelAdmin):
    list_display = ["id", "first_seen", "last_seen", "consented_at"]
    list_filter = ["consented_at"]
    readonly_fields = ["id", "first_seen", "last_seen", "consented_at"]


@admin.register(AnalyticsSession)
class AnalyticsSessionAdmin(admin.ModelAdmin):
    list_display = ["template", "started_at", "duration_seconds", "event_count"]
    list_filter = ["template"]
    search_fields = ["template__name", "template__owner__username"]
    readonly_fields = [
        "visitor",
        "template",
        "started_at",
        "last_seen",
        "ended_at",
        "duration_seconds",
        "entry_path",
        "exit_target",
        "viewport_width",
        "viewport_height",
        "event_count",
    ]


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ["kind", "session", "occurred_at", "target"]
    list_filter = ["kind", "occurred_at"]
    search_fields = ["target", "session__template__name"]
    readonly_fields = [field.name for field in AnalyticsEvent._meta.fields]
