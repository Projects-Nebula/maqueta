from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone
from rest_framework import status

from apps.analytics.constants import (
    CONSENT_ACCEPTED,
    CONSENT_COOKIE,
    CONSENT_DECLINED,
    VISITOR_COOKIE,
)
from apps.analytics.models import AnalyticsEvent, AnalyticsSession, AnalyticsVisitor
from apps.editor.models import UserTemplate

pytestmark = pytest.mark.django_db

CONSENT_URL = "/api/analytics/consent/"
COLLECT_URL = "/api/analytics/collect/"


def _state(title="Public page", text="Hello"):
    return {
        "document": {
            "head": {"title": title, "metas": [], "links": [], "scripts": []},
            "htmlAttributes": {"lang": "en", "dir": "ltr"},
            "doctype": "html",
            "body": {
                "attributes": {},
                "children": [
                    {
                        "type": "element",
                        "tag": "h1",
                        "attributes": {},
                        "children": [{"type": "text", "value": text}],
                    }
                ],
            },
        },
        "styles": {"variables": {}, "rules": [], "mediaQueries": [], "keyframes": []},
        "components": {},
        "assets": {},
    }


def _published(user, slug="public-page", name="Public page"):
    return UserTemplate.objects.create(
        owner=user,
        name=name,
        state=_state(name),
        public_slug=slug,
        is_published=True,
    )


def _accept_consent(client):
    response = client.post(CONSENT_URL, {"decision": CONSENT_ACCEPTED}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert not response.cookies[CONSENT_COOKIE]["httponly"]
    assert response.cookies[VISITOR_COOKIE]["httponly"]
    return response.cookies[VISITOR_COOKIE].value


def _pageview_batch():
    return [
        {
            "kind": "pageview",
            "duration_ms": 0,
            "viewport_width": 1440,
            "viewport_height": 900,
        },
        {
            "kind": "click",
            "x": 0.2,
            "y": 0.3,
            "target": "button#start[button]",
            "viewport_width": 1440,
            "viewport_height": 900,
        },
        {
            "kind": "move",
            "x": 0.21,
            "y": 0.31,
            "viewport_width": 1440,
            "viewport_height": 900,
        },
    ]


def test_consent_is_explicit_and_decline_creates_no_visitor(anon_api):
    response = anon_api.post(CONSENT_URL, {"decision": CONSENT_DECLINED}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"consent": CONSENT_DECLINED}
    assert response.cookies[CONSENT_COOKIE].value == CONSENT_DECLINED
    assert AnalyticsVisitor.objects.count() == 0


def test_collect_requires_consent(anon_api, user):
    template = _published(user)

    response = anon_api.post(
        COLLECT_URL,
        {"template_slug": template.public_slug, "events": _pageview_batch()},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert AnalyticsSession.objects.count() == 0


def test_collect_records_session_duration_and_safe_interactions(anon_api, user):
    template = _published(user)
    visitor_id = _accept_consent(anon_api)

    response = anon_api.post(
        COLLECT_URL,
        {
            "template_slug": template.public_slug,
            "entry_path": "/landing/?utm_source=private-value",
            "events": _pageview_batch(),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    session_id = response.data["session_id"]
    session = AnalyticsSession.objects.get(pk=session_id)
    assert str(session.visitor_id) == visitor_id
    assert session.entry_path == "/landing/"
    assert session.event_count == 3
    assert AnalyticsEvent.objects.filter(session=session).count() == 3

    exit_response = anon_api.post(
        COLLECT_URL,
        {
            "template_slug": template.public_slug,
            "session_id": session_id,
            "events": [
                {"kind": "heartbeat", "duration_ms": 1250},
                {"kind": "page_exit", "duration_ms": 1500, "target": "a#contact"},
            ],
        },
        format="json",
    )

    assert exit_response.status_code == status.HTTP_200_OK
    session.refresh_from_db()
    assert session.event_count == 5
    assert session.duration_seconds >= 1
    assert session.ended_at is not None
    assert session.exit_target == "a#contact"
    assert AnalyticsVisitor.objects.get(pk=visitor_id).consented_at is not None


@pytest.mark.parametrize(
    "event,detail",
    [
        ({"kind": "pageview", "target": "input[value=secret]"}, "invalid target"),
        ({"kind": "pageview", "x": 2}, "invalid x"),
        ({"kind": "pageview", "x": "NaN"}, "invalid x"),
        ({"kind": "unknown"}, "invalid event kind"),
    ],
)
def test_collect_rejects_unsafe_or_invalid_event_values(anon_api, user, event, detail):
    template = _published(user)
    _accept_consent(anon_api)

    response = anon_api.post(
        COLLECT_URL,
        {"template_slug": template.public_slug, "events": [event]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert detail in response.data["detail"]
    assert AnalyticsEvent.objects.count() == 0


def test_collect_rejects_unknown_session(anon_api, user):
    template = _published(user)
    _accept_consent(anon_api)

    response = anon_api.post(
        COLLECT_URL,
        {
            "template_slug": template.public_slug,
            "session_id": "00000000-0000-0000-0000-000000000000",
            "events": _pageview_batch(),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "unknown session"


def test_analytics_api_is_owner_scoped(api, other_api, user, other_user):
    own_template = _published(user, slug="own-page", name="Own page")
    other_template = _published(other_user, slug="other-page", name="Other page")
    own_visitor = AnalyticsVisitor.objects.create(consented_at=timezone.now())
    other_visitor = AnalyticsVisitor.objects.create(consented_at=timezone.now())
    own_session = AnalyticsSession.objects.create(
        visitor=own_visitor,
        template=own_template,
        last_seen=timezone.now(),
        duration_seconds=42,
        viewport_width=1280,
        viewport_height=720,
    )
    other_session = AnalyticsSession.objects.create(
        visitor=other_visitor,
        template=other_template,
        last_seen=timezone.now(),
        duration_seconds=99,
    )
    AnalyticsEvent.objects.create(session=own_session, kind=AnalyticsEvent.Kind.PAGEVIEW)
    AnalyticsEvent.objects.create(
        session=own_session,
        kind=AnalyticsEvent.Kind.CLICK,
        x=Decimal("0.10"),
        y=Decimal("0.10"),
        target="button#start",
    )
    AnalyticsEvent.objects.create(
        session=own_session,
        kind=AnalyticsEvent.Kind.MOVE,
        x=Decimal("0.11"),
        y=Decimal("0.12"),
    )
    AnalyticsEvent.objects.create(session=other_session, kind=AnalyticsEvent.Kind.PAGEVIEW)

    overview = api.get("/api/analytics/overview/?days=365")
    assert overview.status_code == status.HTTP_200_OK
    assert overview.data["metrics"]["visitors"] == 1
    assert overview.data["metrics"]["sessions"] == 1
    assert overview.data["metrics"]["clicks"] == 1
    assert [item["slug"] for item in overview.data["templates"]] == [own_template.public_slug]

    sessions = api.get("/api/analytics/sessions/?days=365")
    assert sessions.status_code == status.HTTP_200_OK
    assert [item["template"] for item in sessions.data["sessions"]] == [own_template.name]

    heatmap = api.get("/api/analytics/heatmap/?days=365&kind=all")
    assert heatmap.status_code == status.HTTP_200_OK
    assert heatmap.data["points"] == [
        {"x": 0.10416666666666667, "y": 0.10416666666666667, "weight": 4, "clicks": 1, "moves": 1}
    ]

    other_overview = other_api.get("/api/analytics/overview/?days=365")
    assert other_overview.data["metrics"]["sessions"] == 1
    assert other_overview.data["templates"][0]["slug"] == other_template.public_slug


def test_heatmap_normalizes_invalid_kind_to_all(api, user):
    response = api.get("/api/analytics/heatmap/?kind=not-a-kind")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["kind"] == "all"


def test_dashboard_requires_authentication(anon_api):
    dashboard = anon_api.get("/analytics/")
    overview = anon_api.get("/api/analytics/overview/")

    assert dashboard.status_code == status.HTTP_302_FOUND
    assert "/login/" in dashboard["Location"]
    assert overview.status_code == status.HTTP_403_FORBIDDEN


def test_dashboard_renders_for_authenticated_user(user):
    # Regression: dashboard.html's nav previously linked storefront:products/
    # payment-config, which raises NoReverseMatch now that apps.storefront
    # is gone — manage.py check never catches {% url %} tags, only a real
    # render does.
    client = Client()
    client.force_login(user)

    response = client.get("/analytics/")

    assert response.status_code == 200


def test_purge_analytics_deletes_expired_sessions_and_orphan_visitors(user):
    template = _published(user)
    old = timezone.now() - timedelta(days=31)
    visitor = AnalyticsVisitor.objects.create(consented_at=old)
    session = AnalyticsSession.objects.create(visitor=visitor, template=template, last_seen=old)
    AnalyticsEvent.objects.create(session=session, kind=AnalyticsEvent.Kind.PAGEVIEW)
    AnalyticsSession.objects.filter(pk=session.pk).update(started_at=old, last_seen=old)
    AnalyticsVisitor.objects.filter(pk=visitor.pk).update(first_seen=old, last_seen=old)
    orphan = AnalyticsVisitor.objects.create(consented_at=old)
    AnalyticsVisitor.objects.filter(pk=orphan.pk).update(first_seen=old, last_seen=old)

    call_command("purge_analytics", days=30)

    assert not AnalyticsSession.objects.filter(pk=session.pk).exists()
    assert not AnalyticsEvent.objects.filter(session_id=session.pk).exists()
    assert not AnalyticsVisitor.objects.filter(pk=visitor.pk).exists()
    assert not AnalyticsVisitor.objects.filter(pk=orphan.pk).exists()


def test_purge_analytics_rejects_non_positive_retention(user):
    with pytest.raises(CommandError, match="at least 1"):
        call_command("purge_analytics", days=0)
