"""Hotmart OAuth connect/callback/disconnect views + page shell (see
openspec design: hotmart-oauth-connect, "Data Flow" section). No token
ever reaches a template, response body, or log line — see design doc's
Security Approach and the spec's "No Token Exposure" requirement.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .client import HotmartClientError, build_hotmart_client
from .models import HotmartConnection
from .oauth import build_authorize_url, consume_state, issue_state

logger = logging.getLogger(__name__)


@login_required
def connection_view(request):
    """/hotmart/ — connection status page shell. All CRUD happens
    client-side against /api/hotmart/* (static/hotmart/connection.js).
    The catalog/link UI lands in a later PR; this shell only shows
    connect/disconnect for now."""
    connected = HotmartConnection.objects.filter(owner=request.user).exists()
    return render(request, "hotmart/connection.html", {"connected": connected})


@login_required
@require_http_methods(["GET"])
def connect_view(request):
    """/hotmart/conectar/ — issues a signed, session-bound, single-use
    state and redirects to Hotmart's authorize endpoint. There is no
    next/return_to param anywhere in this flow (design ADR: the
    post-callback destination is a hardcoded reverse())."""
    state = issue_state(request)
    authorize_url = build_authorize_url(request, state)
    return HttpResponseRedirect(authorize_url)


@login_required
@require_http_methods(["GET"])
def callback_view(request):
    """/hotmart/callback/ — verifies state, exchanges the code for
    tokens server-side, and stores them encrypted on the user's
    HotmartConnection. Any state failure -> 400, no token exchange
    attempted, no row created (spec: "Invalid or expired state")."""
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")

    if not consume_state(request, state):
        return HttpResponseBadRequest("invalid or expired state")

    if not code:
        return HttpResponseBadRequest("missing code")

    client = build_hotmart_client()
    try:
        tokens = client.exchange_code(code)
    except HotmartClientError:
        logger.exception("hotmart token exchange failed")
        return HttpResponseBadRequest("token exchange failed")

    connection, _created = HotmartConnection.objects.get_or_create(owner=request.user)
    connection.set_tokens(
        access=tokens.access_token,
        refresh=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )
    connection.save()

    messages.success(request, "Tu cuenta de Hotmart fue conectada correctamente.")
    return HttpResponseRedirect(reverse("hotmart:connection"))


class DisconnectView(APIView):
    """POST /api/hotmart/disconnect/ — deletes the connection row
    (cascades any product links). Owner-scoped via request.user, same
    IsAuthenticated contract as the rest of the design's API surface."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        HotmartConnection.objects.filter(owner=request.user).delete()
        return Response(status=204)
