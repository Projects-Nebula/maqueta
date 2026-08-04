"""Data migration: strips the retired storefront buy-markup out of every
`UserTemplate.state` (see 0014_drop_storefront_tables.py for the schema-level
tombstone this follows). A seller's saved template may still embed a
`data-buy-form` form or a bare `/comprar/...` anchor from before slice 1/4 of
"remove storefront payments" replaced the checkout flow with a plain
paste-your-own-URL CTA; those markers are now 404s and must not survive a
migrate.

Kept separate from 0014 on purpose: this is an ORM-level JSON rewrite over
`apps.editor.UserTemplate`, unrelated to whether `apps.storefront`'s Python
package or tables still exist, so it doesn't need to run inside the same
atomic DDL step.

Forward-only by design (reverse = noop): there is no way to know what an
already-neutralized `/comprar/` markup used to be, and re-introducing a dead
checkout link on rollback would be actively worse than leaving it removed.

Cheap prefilter (`json.dumps(state)` substring check) skips any row with no
buy markup at all before paying for the recursive walk — a no-op on a fresh
DB or on templates that never had buy markup. Writes go through
`.filter(pk=pk).update(state=new_state)` (not `.save()`) so `updated_at`
(`auto_now=True`) is not bumped and a second run over an already-clean row is
a true no-op (byte-identical state, no write at all).
"""

import json
from copy import deepcopy

from django.db import migrations

MARKERS = ("data-buy-form", "data-product-id", "/comprar/")


def _promote_submit_button_to_anchor(node):
    """Mirrors static/editor/cta-link.js's promoteButtonToAnchor: a
    `<button type="submit">` inside a neutralized buy-form becomes a plain
    `<a href="#">`, keeping its classes/children (i.e. its label text)
    untouched."""
    node["tag"] = "a"
    attributes = node.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}
        node["attributes"] = attributes
    attributes.pop("type", None)
    attributes["href"] = "#"


def _walk(node):
    if not isinstance(node, dict) or node.get("type") != "element":
        return
    attributes = node.get("attributes")
    neutralized_form = False
    if isinstance(attributes, dict):
        attributes.pop("data-buy-form", None)
        attributes.pop("data-product-id", None)

        action = attributes.get("action")
        if isinstance(action, str) and action.startswith("/comprar/"):
            attributes.pop("action", None)
            attributes.pop("method", None)
            if node.get("tag") == "form":
                node["tag"] = "div"
                neutralized_form = True

        href = attributes.get("href")
        if isinstance(href, str) and href.startswith("/comprar/"):
            attributes["href"] = "#"

        if neutralized_form:
            for child in node.get("children") or []:
                if not isinstance(child, dict) or child.get("type") != "element":
                    continue
                child_attributes = child.get("attributes") or {}
                if child.get("tag") == "button" and child_attributes.get("type") == "submit":
                    _promote_submit_button_to_anchor(child)

    for child in node.get("children") or []:
        _walk(child)


def clean_legacy_buy_markup(apps, schema_editor):
    UserTemplate = apps.get_model("editor", "UserTemplate")
    for template in UserTemplate.objects.all().iterator():
        state = template.state
        if not isinstance(state, dict):
            continue
        if not any(marker in json.dumps(state) for marker in MARKERS):
            continue  # cheap prefilter — no buy markup at all, skip the walk

        new_state = deepcopy(state)
        body = (new_state.get("document") or {}).get("body") or {}
        for child in body.get("children") or []:
            _walk(child)

        if new_state != state:
            UserTemplate.objects.filter(pk=template.pk).update(state=new_state)


class Migration(migrations.Migration):
    dependencies = [
        ("editor", "0014_drop_storefront_tables"),
    ]

    operations = [
        migrations.RunPython(clean_legacy_buy_markup, migrations.RunPython.noop),
    ]
