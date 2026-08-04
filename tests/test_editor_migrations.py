"""Tombstone migration coverage: `apps/editor` drops the two Hotmart tables
(and purges their `django_migrations` rows) regardless of whether the
Hotmart app ever ran its own migrations in this database. See design.md
"Migration mechanism — tombstone migration in apps.editor"."""

import copy
import importlib
import json

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from apps.editor.models import UserTemplate

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


CLEAN_LEGACY_BUY_MARKUP_MODULE = "apps.editor.migrations.0015_clean_legacy_buy_markup"


def _base_state(*children):
    return {
        "document": {
            "body": {"attributes": {}, "children": list(children)},
            "head": {},
        },
        "styles": {"variables": {}, "rules": [], "keyframes": []},
        "components": {},
        "assets": {},
    }


def _run_clean_legacy_buy_markup():
    module = importlib.import_module(CLEAN_LEGACY_BUY_MARKUP_MODULE)
    module.clean_legacy_buy_markup(django_apps, None)


def test_clean_legacy_buy_markup_migrates_a_buy_form_to_a_neutral_div(user):
    state = _base_state(
        {
            "type": "element",
            "tag": "form",
            "attributes": {
                "action": "/comprar/5/stripe/",
                "method": "post",
                "data-buy-form": "true",
                "data-product-id": "5",
            },
            "children": [
                {
                    "type": "element",
                    "tag": "button",
                    "attributes": {"type": "submit", "class": ["btn"]},
                    "children": [{"type": "text", "value": "Comprar ahora"}],
                }
            ],
        }
    )
    template = UserTemplate.objects.create(owner=user, name="Buy form card", state=state)

    _run_clean_legacy_buy_markup()

    template.refresh_from_db()
    form_node = template.state["document"]["body"]["children"][0]
    assert form_node["tag"] == "div"
    assert "action" not in form_node["attributes"]
    assert "method" not in form_node["attributes"]
    assert "data-buy-form" not in form_node["attributes"]
    assert "data-product-id" not in form_node["attributes"]

    button_node = form_node["children"][0]
    assert button_node["tag"] == "a"
    assert button_node["attributes"]["href"] == "#"
    assert "type" not in button_node["attributes"]
    assert button_node["children"][0] == {"type": "text", "value": "Comprar ahora"}


def test_clean_legacy_buy_markup_migrates_a_plain_anchor_buy_button(user):
    state = _base_state(
        {
            "type": "element",
            "tag": "a",
            "attributes": {
                "href": "/comprar/5/stripe/",
                "data-buy-form": "true",
                "class": ["btn"],
            },
            "children": [{"type": "text", "value": "Comprar"}],
        }
    )
    template = UserTemplate.objects.create(owner=user, name="Anchor buy button", state=state)

    _run_clean_legacy_buy_markup()

    template.refresh_from_db()
    anchor_node = template.state["document"]["body"]["children"][0]
    assert anchor_node["tag"] == "a"
    assert anchor_node["attributes"]["href"] == "#"
    assert "data-buy-form" not in anchor_node["attributes"]
    assert anchor_node["children"][0] == {"type": "text", "value": "Comprar"}


def test_clean_legacy_buy_markup_leaves_no_comprar_references_anywhere(user):
    state = _base_state(
        {
            "type": "element",
            "tag": "form",
            "attributes": {"action": "/comprar/9/paypal/", "data-buy-form": "true"},
            "children": [
                {
                    "type": "element",
                    "tag": "button",
                    "attributes": {"type": "submit"},
                    "children": [{"type": "text", "value": "Pagar con PayPal"}],
                },
                {
                    "type": "element",
                    "tag": "a",
                    "attributes": {"href": "/comprar/9/paypal/"},
                    "children": [{"type": "text", "value": "Ver detalle"}],
                },
            ],
        }
    )
    template = UserTemplate.objects.create(owner=user, name="Multi-marker card", state=state)

    _run_clean_legacy_buy_markup()

    template.refresh_from_db()
    assert "/comprar/" not in json.dumps(template.state)
    assert "data-buy-form" not in json.dumps(template.state)


def test_clean_legacy_buy_markup_is_idempotent(user):
    state = _base_state(
        {
            "type": "element",
            "tag": "form",
            "attributes": {"action": "/comprar/5/stripe/", "data-buy-form": "true"},
            "children": [
                {
                    "type": "element",
                    "tag": "button",
                    "attributes": {"type": "submit"},
                    "children": [{"type": "text", "value": "Comprar ahora"}],
                }
            ],
        }
    )
    template = UserTemplate.objects.create(owner=user, name="Idempotent card", state=state)

    _run_clean_legacy_buy_markup()
    template.refresh_from_db()
    first_pass_state = copy.deepcopy(template.state)
    first_pass_updated_at = template.updated_at

    _run_clean_legacy_buy_markup()
    template.refresh_from_db()

    assert template.state == first_pass_state
    assert template.updated_at == first_pass_updated_at


def test_clean_legacy_buy_markup_is_a_noop_on_a_template_without_buy_markup(user):
    state = _base_state(
        {
            "type": "element",
            "tag": "h1",
            "attributes": {},
            "children": [{"type": "text", "value": "Bienvenido"}],
        }
    )
    template = UserTemplate.objects.create(owner=user, name="Clean landing", state=state)
    original_state = copy.deepcopy(template.state)
    original_updated_at = template.updated_at

    _run_clean_legacy_buy_markup()

    template.refresh_from_db()
    assert template.state == original_state
    assert template.updated_at == original_updated_at
