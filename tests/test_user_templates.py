from apps.editor.models import UserTemplate
from apps.editor.views import REVISION_RETENTION_LIMIT

URL = "/api/user-templates/"


def _state(marker):
    return {
        "document": {"body": {"attributes": {}, "children": []}, "head": {}},
        "styles": {"variables": {}, "rules": [], "keyframes": []},
        "components": {},
        "assets": {},
        "marker": marker,
    }


def test_update_snapshots_previous_state_as_revision(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    api.patch(f"{URL}{ut.id}/", {"state": _state(1)}, format="json")
    resp = api.get(f"{URL}{ut.id}/revisions/")
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["state"]["marker"] == 0


def test_noop_update_does_not_pad_history(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    api.patch(f"{URL}{ut.id}/", {"state": _state(0)}, format="json")
    resp = api.get(f"{URL}{ut.id}/revisions/")
    assert resp.data == []


def test_revision_history_is_capped_at_retention_limit(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    for i in range(1, REVISION_RETENTION_LIMIT + 6):
        api.patch(f"{URL}{ut.id}/", {"state": _state(i)}, format="json")

    resp = api.get(f"{URL}{ut.id}/revisions/")
    assert resp.status_code == 200
    assert len(resp.data) == REVISION_RETENTION_LIMIT
    # The most recent revisions survive, the oldest ones are pruned.
    versions = sorted(r["version"] for r in resp.data)
    assert versions[0] == 6
    assert versions[-1] == REVISION_RETENTION_LIMIT + 5


def test_template_save_rejects_invalid_palette_metadata(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    invalid = _state(1)
    invalid["styles"] = {
        "palette": {"id": "custom", "name": "Mi paleta", "source": "custom"},
        "variables": {"--color-primary": "#fff"},
    }
    response = api.patch(f"{URL}{ut.id}/", {"state": invalid}, format="json")
    assert response.status_code == 400


def test_valid_custom_palette_survives_save_and_reload(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    custom = _state(1)
    custom["styles"] = {
        "palette": {"id": "mi-marca", "name": "Mi marca", "source": "custom"},
        "variables": {
            "--color-primary": "#112233",
            "--color-background": "#f8fafc",
            "--color-text": "#0f172a",
            "--color-surface": "#ffffff",
        },
        "rules": [],
        "keyframes": [],
    }

    saved = api.patch(f"{URL}{ut.id}/", {"state": custom}, format="json")
    assert saved.status_code == 200

    reloaded = api.get(f"{URL}{ut.id}/")
    assert reloaded.status_code == 200
    assert reloaded.data["state"]["styles"]["palette"] == custom["styles"]["palette"]
    assert reloaded.data["state"]["styles"]["variables"] == custom["styles"]["variables"]
