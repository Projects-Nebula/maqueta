from apps.editor.models import AuditEvent, UserTemplate

URL = "/api/user-templates/"
AUDIT_URL = "/api/audit-events/"


def _state(marker):
    return {
        "document": {"body": {"attributes": {}, "children": []}, "head": {}},
        "styles": {"variables": {}, "rules": [], "keyframes": []},
        "components": {},
        "assets": {},
        "marker": marker,
    }


def test_creating_a_template_writes_an_audit_event(api, user):
    resp = api.post(URL, {"name": "T", "state": _state(0)}, format="json")
    assert resp.status_code == 201
    events = AuditEvent.objects.filter(owner=user)
    assert events.count() == 1
    assert events.first().action == AuditEvent.Action.TEMPLATE_CREATE
    assert events.first().target_id == resp.data["id"]


def test_updating_a_template_state_writes_an_audit_event(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    api.patch(f"{URL}{ut.id}/", {"state": _state(1)}, format="json")
    events = AuditEvent.objects.filter(owner=user, action=AuditEvent.Action.TEMPLATE_SAVE)
    assert events.count() == 1
    assert events.first().target_id == ut.id


def test_noop_update_does_not_write_a_template_save_event(api, user):
    ut = UserTemplate.objects.create(owner=user, name="T", state=_state(0))
    api.patch(f"{URL}{ut.id}/", {"state": _state(0)}, format="json")
    save_events = AuditEvent.objects.filter(owner=user, action=AuditEvent.Action.TEMPLATE_SAVE)
    assert not save_events.exists()


def test_audit_events_are_owner_scoped(api, user, other_user):
    AuditEvent.objects.create(owner=other_user, action=AuditEvent.Action.TEMPLATE_CREATE)
    AuditEvent.objects.create(owner=user, action=AuditEvent.Action.TEMPLATE_CREATE)
    resp = api.get(AUDIT_URL)
    assert resp.status_code == 200
    assert len(resp.data) == 1


def test_audit_events_require_authentication(client):
    resp = client.get(AUDIT_URL)
    assert resp.status_code in (401, 403)


def test_record_prunes_to_retention_limit_per_owner(user, other_user):
    for i in range(AuditEvent.RETENTION_LIMIT + 5):
        AuditEvent.record(owner=user, action=AuditEvent.Action.TEMPLATE_CREATE, metadata={"i": i})
    AuditEvent.record(owner=other_user, action=AuditEvent.Action.TEMPLATE_CREATE)

    assert AuditEvent.objects.filter(owner=user).count() == AuditEvent.RETENTION_LIMIT
    # The most recent survive, the oldest are pruned.
    kept = set(AuditEvent.objects.filter(owner=user).values_list("metadata__i", flat=True))
    assert kept == set(range(5, AuditEvent.RETENTION_LIMIT + 5))
    # Pruning is per-owner — another owner's events are untouched.
    assert AuditEvent.objects.filter(owner=other_user).count() == 1
