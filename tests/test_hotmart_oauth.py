import time
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory

from apps.hotmart.models import HotmartConnection
from apps.hotmart.oauth import build_authorize_url, consume_state, issue_state

pytestmark = pytest.mark.django_db

CONNECT_URL = "/hotmart/conectar/"
CALLBACK_URL = "/hotmart/callback/"
DISCONNECT_URL = "/api/hotmart/disconnect/"


def _session_request():
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    return request


def _extract_state(location):
    return parse_qs(urlparse(location).query)["state"][0]


class TestIssueAndConsumeState:
    def test_consume_state_accepts_freshly_issued_state(self):
        request = _session_request()
        state = issue_state(request)

        assert consume_state(request, state) is True

    def test_consume_state_rejects_tampered_state(self):
        request = _session_request()
        state = issue_state(request)
        tampered = state[:-1] + ("a" if state[-1] != "a" else "b")

        assert consume_state(request, tampered) is False

    def test_consume_state_rejects_expired_state(self, monkeypatch):
        request = _session_request()
        old_time = time.time() - 700
        monkeypatch.setattr("django.core.signing.time.time", lambda: old_time)
        state = issue_state(request)
        monkeypatch.undo()

        assert consume_state(request, state) is False

    def test_consume_state_rejects_replay(self):
        request = _session_request()
        state = issue_state(request)

        assert consume_state(request, state) is True
        assert consume_state(request, state) is False

    def test_consume_state_rejects_cross_session(self):
        request_a = _session_request()
        request_b = _session_request()
        state = issue_state(request_a)

        assert consume_state(request_b, state) is False

    def test_consume_state_rejects_missing_state(self):
        request = _session_request()

        assert consume_state(request, "") is False

    def test_build_authorize_url_includes_state_and_no_next_param(self, settings):
        settings.HOTMART_CLIENT_ID = "client-id"
        settings.HOTMART_AUTH_BASE_URL = "https://auth.example.com/oauth"
        request = RequestFactory().get("/")

        url = build_authorize_url(request, "signed-state-value")

        assert url.startswith("https://auth.example.com/oauth/authorize?")
        assert "state=signed-state-value" in url
        assert "client_id=client-id" in url
        assert "next=" not in url
        assert "return_to" not in url


class TestConnectFlow:
    def test_connect_redirects_to_authorize_with_state(self, user):
        client = Client()
        client.force_login(user)

        response = client.get(CONNECT_URL)

        assert response.status_code == 302
        assert "state=" in response["Location"]

    def test_connect_requires_login(self):
        client = Client()

        response = client.get(CONNECT_URL)

        assert response.status_code in (302, 401, 403)
        if response.status_code == 302:
            assert "login" in response["Location"]

    def test_callback_happy_path_creates_connection(self, user):
        client = Client()
        client.force_login(user)
        connect_response = client.get(CONNECT_URL)
        state = _extract_state(connect_response["Location"])

        callback_response = client.get(CALLBACK_URL, {"code": "some-code", "state": state})

        assert callback_response.status_code == 302
        connection = HotmartConnection.objects.get(owner=user)
        access_token = connection.get_access_token()
        assert access_token
        assert access_token not in callback_response.content.decode()

    def test_callback_rejects_missing_state(self, user):
        client = Client()
        client.force_login(user)

        response = client.get(CALLBACK_URL, {"code": "some-code"})

        assert response.status_code == 400
        assert not HotmartConnection.objects.filter(owner=user).exists()

    def test_callback_rejects_bad_state(self, user):
        client = Client()
        client.force_login(user)
        client.get(CONNECT_URL)

        response = client.get(CALLBACK_URL, {"code": "some-code", "state": "not-a-valid-state"})

        assert response.status_code == 400
        assert not HotmartConnection.objects.filter(owner=user).exists()

    def test_callback_rejects_replayed_state(self, user):
        client = Client()
        client.force_login(user)
        connect_response = client.get(CONNECT_URL)
        state = _extract_state(connect_response["Location"])
        client.get(CALLBACK_URL, {"code": "some-code", "state": state})

        replay_response = client.get(CALLBACK_URL, {"code": "some-other-code", "state": state})

        assert replay_response.status_code == 400
        assert HotmartConnection.objects.filter(owner=user).count() == 1

    def test_disconnect_deletes_connection(self, user):
        client = Client()
        client.force_login(user)
        connection = HotmartConnection.objects.create(owner=user)
        connection.set_tokens(access="a", refresh="r", expires_in=3600)
        connection.save()

        response = client.post(DISCONNECT_URL)

        assert response.status_code in (200, 204)
        assert not HotmartConnection.objects.filter(owner=user).exists()

    def test_disconnect_requires_login(self):
        client = Client()

        response = client.post(DISCONNECT_URL)

        assert response.status_code in (302, 401, 403)
