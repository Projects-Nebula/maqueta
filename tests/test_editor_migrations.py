"""Tombstone migration coverage: `apps/editor` drops the two Hotmart tables
(and purges their `django_migrations` rows) regardless of whether the
Hotmart app ever ran its own migrations in this database. See design.md
"Migration mechanism — tombstone migration in apps.editor"."""

import importlib

import pytest
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

MIGRATION_MODULE = "apps.editor.migrations.0013_drop_hotmart_tables"
HOTMART_TABLES = ("hotmart_hotmartproductlink", "hotmart_hotmartconnection")

STOREFRONT_MIGRATION_MODULE = "apps.editor.migrations.0014_drop_storefront_tables"
STOREFRONT_TABLES = (
    "storefront_order",
    "storefront_product",
    "storefront_paymentgatewayconfig",
)

pytestmark = pytest.mark.django_db


def _reset_hotmart_state():
    """Drop any pre-existing Hotmart tables/recorder rows so each test starts
    from a known state, independent of whether apps.hotmart is still
    installed elsewhere in the migration graph at this point in the change."""
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS hotmart_hotmartproductlink")
        cursor.execute("DROP TABLE IF EXISTS hotmart_hotmartconnection")
    MigrationRecorder(connection).migration_qs.filter(app="hotmart").delete()


def _create_hotmart_tables():
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE hotmart_hotmartconnection (id serial PRIMARY KEY)")
        cursor.execute(
            "CREATE TABLE hotmart_hotmartproductlink ("
            "id serial PRIMARY KEY, "
            "connection_id integer REFERENCES hotmart_hotmartconnection(id))"
        )


def _seed_recorder_rows():
    recorder = MigrationRecorder(connection)
    recorder.migration_qs.create(app="hotmart", name="0001_initial")
    recorder.migration_qs.create(app="hotmart", name="0002_developer_credentials")


def test_drop_hotmart_tables_migration_drops_tables_and_purges_recorder():
    module = importlib.import_module(MIGRATION_MODULE)
    _reset_hotmart_state()
    _create_hotmart_tables()
    _seed_recorder_rows()

    with connection.schema_editor() as schema_editor:
        module.drop_hotmart_tables(None, schema_editor)

    table_names = set(connection.introspection.table_names())
    assert "hotmart_hotmartconnection" not in table_names
    assert "hotmart_hotmartproductlink" not in table_names
    assert not MigrationRecorder(connection).migration_qs.filter(app="hotmart").exists()


def test_drop_hotmart_tables_migration_is_noop_on_fresh_db():
    module = importlib.import_module(MIGRATION_MODULE)
    _reset_hotmart_state()

    # No Hotmart tables and no recorder rows exist — must not raise.
    with connection.schema_editor() as schema_editor:
        module.drop_hotmart_tables(None, schema_editor)

    assert not MigrationRecorder(connection).migration_qs.filter(app="hotmart").exists()


def _reset_storefront_state():
    """Drop any pre-existing storefront tables/recorder rows so each test
    starts from a known state, independent of whether apps.storefront is
    still installed elsewhere in the migration graph at this point in the
    change."""
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS storefront_order")
        cursor.execute("DROP TABLE IF EXISTS storefront_product")
        cursor.execute("DROP TABLE IF EXISTS storefront_paymentgatewayconfig")
    MigrationRecorder(connection).migration_qs.filter(app="storefront").delete()


def _create_storefront_tables():
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE storefront_paymentgatewayconfig (id serial PRIMARY KEY)")
        cursor.execute("CREATE TABLE storefront_product (id serial PRIMARY KEY)")
        cursor.execute(
            "CREATE TABLE storefront_order ("
            "id serial PRIMARY KEY, "
            "product_id integer REFERENCES storefront_product(id))"
        )


def _seed_storefront_recorder_rows():
    recorder = MigrationRecorder(connection)
    recorder.migration_qs.create(app="storefront", name="0001_initial")
    recorder.migration_qs.create(app="storefront", name="0002_multi_gateway_checkout")
    recorder.migration_qs.create(app="storefront", name="0003_alter_order_gateway")


def test_drop_storefront_tables_migration_drops_tables_and_purges_recorder():
    module = importlib.import_module(STOREFRONT_MIGRATION_MODULE)
    _reset_storefront_state()
    _create_storefront_tables()
    _seed_storefront_recorder_rows()

    with connection.schema_editor() as schema_editor:
        module.drop_storefront_tables(None, schema_editor)

    table_names = set(connection.introspection.table_names())
    for table in STOREFRONT_TABLES:
        assert table not in table_names
    assert not MigrationRecorder(connection).migration_qs.filter(app="storefront").exists()


def test_drop_storefront_tables_migration_is_noop_on_fresh_db():
    module = importlib.import_module(STOREFRONT_MIGRATION_MODULE)
    _reset_storefront_state()

    # No storefront tables and no recorder rows exist — must not raise.
    with connection.schema_editor() as schema_editor:
        module.drop_storefront_tables(None, schema_editor)

    assert not MigrationRecorder(connection).migration_qs.filter(app="storefront").exists()
