"""Cron reconciliation entry point (see openspec design:
hotmart-oauth-connect, "sync = shared reconcile function, two triggers" —
mirrors apps/analytics/management/commands/purge_analytics.py). Covers
landings whose owner never logs in to trigger the opportunistic sync on
`/api/hotmart/products/`; both triggers call the exact same
`reconcile_products()` function so behavior never drifts between them.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.hotmart.client import HotmartClientError, build_hotmart_client
from apps.hotmart.models import HotmartConnection
from apps.hotmart.services import HotmartReconnectRequired, ensure_fresh_token, reconcile_products


class Command(BaseCommand):
    help = (
        "Reconcile every Hotmart connection with linked landings against the live "
        "catalog, unpublishing any landing whose product was removed or deactivated "
        "upstream. Fail-safe: a connection whose fetch fails (refresh failure, "
        "timeout, 5xx) is skipped untouched, never treated as 'product gone'."
    )

    def handle(self, *args, **options):
        reconciled = 0
        skipped = 0

        connections = HotmartConnection.objects.filter(product_links__isnull=False).distinct()
        for connection in connections:
            client = build_hotmart_client(connection.get_credentials())
            try:
                access_token = ensure_fresh_token(connection, client)
                products = client.list_products(access_token)
            except (HotmartReconnectRequired, HotmartClientError):
                skipped += 1
                continue
            reconcile_products(connection, products)
            reconciled += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciled {reconciled} connection(s), skipped {skipped} (fetch failed)."
            )
        )
        return 0
