"""OAuth CSRF-state helpers for the Hotmart connect flow (see openspec
design: hotmart-oauth-connect, "state = signed + session-bound +
single-use; no user-supplied redirect" decision).

There is no `OAuthState` DB table and no `next`/`return_to` parameter
anywhere in this module — the post-callback destination is always the
hardcoded `reverse("hotmart:connection")`, so an open redirect is
impossible by construction rather than by validation.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.http import HttpRequest
from django.urls import reverse

_STATE_SESSION_KEY = "hotmart_oauth_nonce"
_STATE_MAX_AGE = 600  # 10 minutes
_STATE_SALT = "apps.hotmart.oauth.state"


def issue_state(request: HttpRequest) -> str:
    """Generates a random nonce, stores it in the session, and returns a
    signed+timestamped token embedding it."""
    nonce = secrets.token_urlsafe(32)
    request.session[_STATE_SESSION_KEY] = nonce
    signer = signing.TimestampSigner(salt=_STATE_SALT)
    return signer.sign(nonce)


def consume_state(request: HttpRequest, state: str) -> bool:
    """Verifies signature, max_age, and that the nonce matches the live
    session value, then pops it from the session so it cannot be
    replayed. Any failure returns False without raising — callers
    respond 400 without attempting a token exchange."""
    if not state:
        return False
    signer = signing.TimestampSigner(salt=_STATE_SALT)
    try:
        nonce = signer.unsign(state, max_age=_STATE_MAX_AGE)
    except signing.BadSignature:
        return False
    session_nonce = request.session.get(_STATE_SESSION_KEY)
    if not session_nonce or not secrets.compare_digest(session_nonce, nonce):
        return False
    del request.session[_STATE_SESSION_KEY]
    return True


def build_authorize_url(request: HttpRequest, state: str) -> str:
    """Builds the full Hotmart authorize URL. `redirect_uri` is built
    from the hardcoded callback route via `reverse()` — it is never
    user-supplied, so there is no open-redirect surface here."""
    redirect_uri = request.build_absolute_uri(reverse("hotmart:callback"))
    params = {
        "response_type": "code",
        "client_id": settings.HOTMART_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{settings.HOTMART_AUTH_BASE_URL}/authorize?{urlencode(params)}"
