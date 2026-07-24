import re
import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .constants import (
    MAX_BATCH_EVENTS,
    MAX_DURATION_MS,
    MAX_EVENTS_PER_SESSION,
    MAX_TARGET_LENGTH,
    MAX_VIEWPORT,
    TRACKED_EVENT_KINDS,
    VISITOR_COOKIE,
)
from .models import AnalyticsEvent, AnalyticsSession, AnalyticsVisitor

TARGET_PATTERN = re.compile(r"^[a-zA-Z0-9_:#.\[\]-]{0,120}$")


class AnalyticsInputError(ValueError):
    pass


def visitor_from_request(request) -> AnalyticsVisitor | None:
    raw_id = request.COOKIES.get(VISITOR_COOKIE)
    if not raw_id:
        return None
    try:
        visitor_id = uuid.UUID(raw_id)
    except (ValueError, AttributeError):
        return None
    return AnalyticsVisitor.objects.filter(pk=visitor_id).first()


def create_consented_visitor() -> AnalyticsVisitor:
    return AnalyticsVisitor.objects.create(consented_at=timezone.now())


def _clean_path(value) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        return "/"
    return value.split("?", 1)[0].split("#", 1)[0][:200] or "/"


def _clean_decimal(value, field_name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise AnalyticsInputError(f"invalid {field_name}") from exc
    if not number.is_finite() or number < 0 or number > 1:
        raise AnalyticsInputError(f"invalid {field_name}")
    return number.quantize(Decimal("0.00001"))


def _clean_int(value, field_name: str, maximum: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AnalyticsInputError(f"invalid {field_name}")
    try:
        number = int(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise AnalyticsInputError(f"invalid {field_name}") from exc
    if number < 0 or number > maximum:
        raise AnalyticsInputError(f"invalid {field_name}")
    return number


def clean_events(raw_events) -> list[dict]:
    if not isinstance(raw_events, list) or not raw_events:
        raise AnalyticsInputError("events must be a non-empty list")
    if len(raw_events) > MAX_BATCH_EVENTS:
        raise AnalyticsInputError("too many events")

    cleaned = []
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            raise AnalyticsInputError("invalid event")
        kind = raw_event.get("kind")
        if kind not in TRACKED_EVENT_KINDS:
            raise AnalyticsInputError("invalid event kind")

        target = raw_event.get("target", "")
        if not isinstance(target, str) or len(target) > MAX_TARGET_LENGTH:
            raise AnalyticsInputError("invalid target")
        if not TARGET_PATTERN.fullmatch(target):
            raise AnalyticsInputError("invalid target")

        cleaned.append(
            {
                "kind": kind,
                "x": _clean_decimal(raw_event.get("x"), "x"),
                "y": _clean_decimal(raw_event.get("y"), "y"),
                "target": target,
                "duration_ms": _clean_int(
                    raw_event.get("duration_ms"), "duration_ms", MAX_DURATION_MS
                ),
                "viewport_width": _clean_int(
                    raw_event.get("viewport_width"), "viewport_width", MAX_VIEWPORT
                ),
                "viewport_height": _clean_int(
                    raw_event.get("viewport_height"), "viewport_height", MAX_VIEWPORT
                ),
            }
        )
    return cleaned


@transaction.atomic
def record_events(
    *, visitor, template, session_id, entry_path, events
) -> tuple[AnalyticsSession, int]:
    """Persist a bounded event batch for a consented visitor/template pair."""
    events = clean_events(events)
    now = timezone.now()
    session = None
    if session_id:
        try:
            parsed_session_id = uuid.UUID(str(session_id))
        except (ValueError, AttributeError) as exc:
            raise AnalyticsInputError("invalid session_id") from exc
        session = (
            AnalyticsSession.objects.select_for_update()
            .filter(pk=parsed_session_id, visitor=visitor, template=template)
            .first()
        )
        if session is None:
            raise AnalyticsInputError("unknown session")

    if session is None:
        if events[0]["kind"] != AnalyticsEvent.Kind.PAGEVIEW:
            raise AnalyticsInputError("first event must be pageview")
        first_event = events[0]
        session = AnalyticsSession.objects.create(
            visitor=visitor,
            template=template,
            last_seen=now,
            entry_path=_clean_path(entry_path),
            viewport_width=first_event["viewport_width"],
            viewport_height=first_event["viewport_height"],
        )

    remaining = max(0, MAX_EVENTS_PER_SESSION - session.event_count)
    accepted_events = events[:remaining]
    if accepted_events:
        AnalyticsEvent.objects.bulk_create(
            [AnalyticsEvent(session=session, **event) for event in accepted_events]
        )

    duration_ms = (
        max((event["duration_ms"] or 0) for event in accepted_events) if accepted_events else 0
    )
    elapsed_seconds = max(0, int((now - session.started_at).total_seconds()))
    session.last_seen = now
    session.duration_seconds = max(session.duration_seconds, duration_ms // 1000, elapsed_seconds)
    session.event_count += len(accepted_events)
    for event in reversed(accepted_events):
        if event["kind"] == AnalyticsEvent.Kind.PAGE_EXIT:
            session.ended_at = now
            session.exit_target = event["target"]
            break
    session.save(
        update_fields=[
            "last_seen",
            "duration_seconds",
            "event_count",
            "ended_at",
            "exit_target",
        ]
    )
    AnalyticsVisitor.objects.filter(pk=visitor.pk).update(last_seen=now)
    return session, len(accepted_events)
