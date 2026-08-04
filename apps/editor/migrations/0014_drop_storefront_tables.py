"""Tombstone migration: drops the storefront/payments tables and purges
their django_migrations rows, regardless of whether apps.storefront ever
ran its own migrations in this database. Hosted in apps.editor (not
apps.storefront) because it must survive apps.storefront's removal — see
0013_drop_hotmart_tables.py and design.md "Migration mechanism — tombstone
migration in apps.editor" for the rejected alternatives (a final
DeleteModel migration inside the dying app leaves orphan django_migrations
rows; a documented `migrate storefront zero` runbook step is a manual,
skippable footgun).

Idempotent and safe to run on any database: no-ops if the tables were never
created, and the reverse migration is an explicit no-op — dropped rows are
not recoverable (test/dev data only, confirmed in the resolved proposal).
Drop order is child-first (storefront_order has an FK to storefront_product)
to avoid a Postgres FK-dependency failure without CASCADE;
storefront_paymentgatewayconfig has no intra-app parent.
"""

from django.db import migrations
from django.db.migrations.recorder import MigrationRecorder

STOREFRONT_TABLES = (
    "storefront_order",
    "storefront_product",
    "storefront_paymentgatewayconfig",
)


def drop_storefront_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())
    for table in STOREFRONT_TABLES:
        if table in existing:
            schema_editor.execute(f"DROP TABLE {connection.ops.quote_name(table)}")
    MigrationRecorder(connection).migration_qs.filter(app="storefront").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("editor", "0013_drop_hotmart_tables"),
    ]

    operations = [
        migrations.RunPython(drop_storefront_tables, migrations.RunPython.noop),
    ]
