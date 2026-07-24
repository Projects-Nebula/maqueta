from django.conf import settings

VISITOR_COOKIE = "analytics_visitor_id"
CONSENT_COOKIE = "analytics_consent"
CONSENT_ACCEPTED = "accepted"
CONSENT_DECLINED = "declined"

MAX_BATCH_EVENTS = 80
MAX_EVENTS_PER_SESSION = 1200
MAX_TARGET_LENGTH = 120
MAX_DURATION_MS = 24 * 60 * 60 * 1000
MAX_VIEWPORT = 10_000
ANALYTICS_COOKIE_MAX_AGE = getattr(settings, "ANALYTICS_COOKIE_MAX_AGE", 60 * 60 * 24 * 365)

TRACKED_EVENT_KINDS = {
    "pageview",
    "heartbeat",
    "click",
    "move",
    "page_exit",
}
