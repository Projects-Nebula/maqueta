"""Tombstone migration: drops the Hotmart tables and purges their
django_migrations rows, regardless of whether apps.hotmart ever ran its own
migrations in this database. Hosted in apps.editor (not apps.hotmart)
because it must survive apps.hotmart's removal — see design.md "Migration
mechanism — tombstone migration in apps.editor" for the rejected
alternatives (a final DeleteModel migration inside the dying app leaves
orphan django_migrations rows; a documented `migrate hotmart zero` runbook
step is a manual, skippable footgun).

Idempotent and safe to run on any database: no-ops if the tables were never
created, and the reverse migration is an explicit no-op — dropped rows are
not recoverable (test/dev data only, confirmed in the resolved proposal).
"""

from django.db import migrations
from django.db.migrations.recorder import MigrationRecorder

HOTMART_TABLES = ("hotmart_hotmartproductlink", "hotmart_hotmartconnection")


def drop_hotmart_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())
    for table in HOTMART_TABLES:
        if table in existing:
            schema_editor.execute(f"DROP TABLE {connection.ops.quote_name(table)}")
    MigrationRecorder(connection).migration_qs.filter(app="hotmart").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("editor", "0012_sitebundle_is_active"),
    ]

    operations = [
        migrations.RunPython(drop_hotmart_tables, migrations.RunPython.noop),
    ]
