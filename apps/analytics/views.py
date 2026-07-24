from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.editor.models import UserTemplate

from .constants import (
    ANALYTICS_COOKIE_MAX_AGE,
    CONSENT_ACCEPTED,
    CONSENT_COOKIE,
    CONSENT_DECLINED,
    VISITOR_COOKIE,
)
from .models import AnalyticsEvent, AnalyticsSession
from .services import (
    AnalyticsInputError,
    create_consented_visitor,
    record_events,
    visitor_from_request,
)


def _cookie_options(request, *, http_only):
    return {
        "max_age": ANALYTICS_COOKIE_MAX_AGE,
        "secure": request.is_secure(),
        "httponly": http_only,
        "samesite": "Lax",
        "path": "/",
    }


@method_decorator(csrf_exempt, name="dispatch")
class AnalyticsConsentView(APIView):
    """Record a public visitor's analytics choice and set only first-party cookies."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics_consent"

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({"error": "invalid_payload"}, status=400)
        decision = request.data.get("decision")
        if not isinstance(decision, str) or decision not in {
            CONSENT_ACCEPTED,
            CONSENT_DECLINED,
        }:
            return Response({"error": "invalid_decision"}, status=400)

        response = Response({"consent": decision})
        response.set_cookie(
            CONSENT_COOKIE,
            decision,
            **_cookie_options(request, http_only=False),
        )
        if decision == CONSENT_DECLINED:
            response.delete_cookie(VISITOR_COOKIE, path="/")
            return response

        visitor = visitor_from_request(request)
        if visitor is None:
            visitor = create_consented_visitor()
        elif visitor.consented_at is None:
            visitor.consented_at = timezone.now()
            visitor.save(update_fields=["consented_at"])
        response.set_cookie(
            VISITOR_COOKIE,
            str(visitor.pk),
            **_cookie_options(request, http_only=True),
        )
        return response


@method_decorator(csrf_exempt, name="dispatch")
class AnalyticsCollectView(APIView):
    """Receive a bounded batch from a consented public template visitor."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics_collect"

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({"error": "invalid_payload"}, status=400)
        if request.COOKIES.get(CONSENT_COOKIE) != CONSENT_ACCEPTED:
            return Response({"error": "consent_required"}, status=403)
        visitor = visitor_from_request(request)
        if visitor is None or visitor.consented_at is None:
            return Response({"error": "consent_required"}, status=403)

        template_slug = request.data.get("template_slug")
        if not isinstance(template_slug, str) or not template_slug or len(template_slug) > 140:
            return Response({"error": "invalid_template"}, status=400)
        template = UserTemplate.objects.filter(
            public_slug=template_slug,
            is_published=True,
        ).first()
        if template is None:
            raise Http404

        try:
            session, accepted = record_events(
                visitor=visitor,
                template=template,
                session_id=request.data.get("session_id"),
                entry_path=request.data.get("entry_path", "/"),
                events=request.data.get("events"),
            )
        except AnalyticsInputError as exc:
            return Response({"error": "invalid_event_batch", "detail": str(exc)}, status=400)
        return Response({"session_id": str(session.pk), "accepted": accepted})


def _period_start(request):
    try:
        days = int(request.query_params.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    return timezone.now() - timedelta(days=days), days


def _owned_sessions(request, start):
    sessions = AnalyticsSession.objects.filter(
        template__owner=request.user,
        started_at__gte=start,
    )
    slug = request.query_params.get("template")
    if slug:
        sessions = sessions.filter(template__public_slug=slug)
    return sessions


class AnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start, days = _period_start(request)
        sessions = _owned_sessions(request, start)
        event_filter = Q(session__in=sessions)
        aggregates = sessions.aggregate(
            sessions=Count("id"),
            visitors=Count("visitor_id", distinct=True),
            average_duration=Avg("duration_seconds"),
        )
        event_counts = AnalyticsEvent.objects.filter(event_filter).aggregate(
            pageviews=Count("id", filter=Q(kind=AnalyticsEvent.Kind.PAGEVIEW)),
            clicks=Count("id", filter=Q(kind=AnalyticsEvent.Kind.CLICK)),
            move_samples=Count("id", filter=Q(kind=AnalyticsEvent.Kind.MOVE)),
        )
        templates = (
            UserTemplate.objects.filter(owner=request.user)
            .annotate(
                sessions_count=Count(
                    "analytics_sessions",
                    filter=Q(analytics_sessions__started_at__gte=start),
                )
            )
            .order_by("name")
        )
        return Response(
            {
                "days": days,
                "metrics": {
                    "visitors": aggregates["visitors"] or 0,
                    "sessions": aggregates["sessions"] or 0,
                    "pageviews": event_counts["pageviews"] or 0,
                    "clicks": event_counts["clicks"] or 0,
                    "move_samples": event_counts["move_samples"] or 0,
                    "average_duration_seconds": round(
                        float(aggregates["average_duration"] or 0), 1
                    ),
                },
                "templates": [
                    {
                        "slug": template.public_slug,
                        "name": template.name,
                        "is_published": template.is_published,
                        "sessions": template.sessions_count,
                    }
                    for template in templates
                ],
            }
        )


class AnalyticsSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start, _days = _period_start(request)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 50)), 100))
        except (TypeError, ValueError):
            limit = 50
        sessions = (
            _owned_sessions(request, start)
            .select_related("template")
            .annotate(
                pageviews=Count("events", filter=Q(events__kind=AnalyticsEvent.Kind.PAGEVIEW)),
                clicks=Count("events", filter=Q(events__kind=AnalyticsEvent.Kind.CLICK)),
                move_samples=Count("events", filter=Q(events__kind=AnalyticsEvent.Kind.MOVE)),
            )[:limit]
        )
        return Response(
            {
                "sessions": [
                    {
                        "id": str(session.pk)[:8],
                        "template": session.template.name,
                        "started_at": session.started_at.isoformat(),
                        "last_seen": session.last_seen.isoformat(),
                        "duration_seconds": session.duration_seconds,
                        "pageviews": session.pageviews,
                        "clicks": session.clicks,
                        "move_samples": session.move_samples,
                        "exit_target": session.exit_target,
                        "viewport": {
                            "width": session.viewport_width,
                            "height": session.viewport_height,
                        },
                    }
                    for session in sessions
                ]
            }
        )


class AnalyticsHeatmapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start, days = _period_start(request)
        sessions = _owned_sessions(request, start)
        requested_kind = request.query_params.get("kind", "all")
        kinds_by_name = {
            "click": [AnalyticsEvent.Kind.CLICK],
            "move": [AnalyticsEvent.Kind.MOVE],
            "all": [AnalyticsEvent.Kind.CLICK, AnalyticsEvent.Kind.MOVE],
        }
        selected_kind = requested_kind if requested_kind in kinds_by_name else "all"
        kinds = kinds_by_name[selected_kind]
        events = (
            AnalyticsEvent.objects.filter(session__in=sessions, kind__in=kinds)
            .exclude(x__isnull=True)
            .exclude(y__isnull=True)
            .values("x", "y", "kind")[:20_000]
        )
        grid_size = 24
        buckets = {}
        for event in events:
            bucket_x = min(grid_size - 1, int(float(event["x"]) * grid_size))
            bucket_y = min(grid_size - 1, int(float(event["y"]) * grid_size))
            key = (bucket_x, bucket_y)
            bucket = buckets.setdefault(
                key,
                {
                    "x": (bucket_x + 0.5) / grid_size,
                    "y": (bucket_y + 0.5) / grid_size,
                    "weight": 0,
                    "clicks": 0,
                    "moves": 0,
                },
            )
            weight = 3 if event["kind"] == AnalyticsEvent.Kind.CLICK else 1
            bucket["weight"] += weight
            bucket["clicks"] += int(event["kind"] == AnalyticsEvent.Kind.CLICK)
            bucket["moves"] += int(event["kind"] == AnalyticsEvent.Kind.MOVE)
        return Response({"days": days, "kind": selected_kind, "points": list(buckets.values())})


@login_required
def analytics_dashboard_view(request):
    return render(request, "analytics/dashboard.html")
