from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.analytics.models import AnalyticsSession, AnalyticsVisitor


class Command(BaseCommand):
    help = "Delete anonymous analytics data older than the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = getattr(settings, "ANALYTICS_RETENTION_DAYS", 90)
        if days < 1:
            raise CommandError("--days must be at least 1")

        cutoff = timezone.now() - timedelta(days=days)
        deleted_sessions, _ = AnalyticsSession.objects.filter(last_seen__lt=cutoff).delete()
        deleted_visitors, _ = AnalyticsVisitor.objects.filter(
            last_seen__lt=cutoff,
            sessions__isnull=True,
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_sessions} analytics rows and {deleted_visitors} stale visitors."
            )
        )
        return 0
