"""RED tests for apps/hotmart/models.py credential storage and the
POST /api/hotmart/credentials/ validate-before-persist endpoint (see
design's "validate against Hotmart before persisting" decision).
"""

import logging

import pytest

from apps.hotmart.client import HotmartClientError, TokenBundle
from apps.hotmart.models import HotmartConnection

pytestmark = pytest.mark.django_db

CREDENTIALS_URL = "/api/hotmart/credentials/"


class _FakeValidatingClient:
    def __init__(self, *, should_succeed: bool):
        self._should_succeed = should_succeed

    def fetch_token(self):
        if not self._should_succeed:
            raise HotmartClientError("invalid credentials")
        return TokenBundle(access_token="validated-access-token", expires_in=3600)


class TestCredentialStorage:
    def test_set_get_credentials_round_trip(self, user):
        connection = HotmartConnection.objects.create(owner=user)

        connection.set_credentials({"client_id": "id-1", "client_secret": "secret-1"})

        assert connection.credentials_encrypted != ""
        assert "id-1" not in connection.credentials_encrypted
        assert "secret-1" not in connection.credentials_encrypted
        assert connection.get_credentials() == {"client_id": "id-1", "client_secret": "secret-1"}

    def test_has_credentials_false_when_none_stored(self, user):
        connection = HotmartConnection.objects.create(owner=user)

        assert connection.has_credentials() is False

    def test_has_credentials_true_when_both_present(self, user):
        connection = HotmartConnection.objects.create(owner=user)
        connection.set_credentials({"client_id": "id-1", "client_secret": "secret-1"})

        assert connection.has_credentials() is True

    def test_has_credentials_false_when_only_one_present(self, user):
        connection = HotmartConnection.objects.create(owner=user)
        connection.set_credentials({"client_id": "id-1", "client_secret": ""})

        assert connection.has_credentials() is False


class TestCredentialsView:
    def test_post_valid_credentials_stores_and_returns_200(self, api, user, monkeypatch):
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client",
            lambda credentials: _FakeValidatingClient(should_succeed=True),
        )

        response = api.post(
            CREDENTIALS_URL,
            {"client_id": "id-1", "client_secret": "secret-1"},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["connected"] is True
        assert response.data["has_credentials"] == {"client_id": True, "client_secret": True}
        connection = HotmartConnection.objects.get(owner=user)
        assert connection.get_credentials() == {"client_id": "id-1", "client_secret": "secret-1"}
        assert connection.get_access_token() == "validated-access-token"

    def test_post_invalid_credentials_returns_400_and_persists_nothing(
        self, api, user, monkeypatch
    ):
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client",
            lambda credentials: _FakeValidatingClient(should_succeed=False),
        )

        response = api.post(
            CREDENTIALS_URL,
            {"client_id": "bad-id", "client_secret": "bad-secret"},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error"] == "invalid_credentials"
        assert not HotmartConnection.objects.filter(owner=user).exists()

    def test_response_never_contains_credential_values(self, api, user, monkeypatch):
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client",
            lambda credentials: _FakeValidatingClient(should_succeed=True),
        )

        response = api.post(
            CREDENTIALS_URL,
            {"client_id": "secret-id-1", "client_secret": "secret-value-1"},
            format="json",
        )

        body = str(response.data)
        assert "secret-id-1" not in body
        assert "secret-value-1" not in body

    def test_log_never_contains_credential_values(self, api, user, monkeypatch, caplog):
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client",
            lambda credentials: _FakeValidatingClient(should_succeed=False),
        )

        with caplog.at_level(logging.INFO):
            api.post(
                CREDENTIALS_URL,
                {"client_id": "leak-id", "client_secret": "leak-secret"},
                format="json",
            )

        assert "leak-id" not in caplog.text
        assert "leak-secret" not in caplog.text

    def test_rotating_one_credential_keeps_the_other(self, api, user, monkeypatch):
        connection = HotmartConnection.objects.create(owner=user)
        connection.set_credentials({"client_id": "original-id", "client_secret": "original-secret"})
        connection.save()
        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client",
            lambda credentials: _FakeValidatingClient(should_succeed=True),
        )

        response = api.post(CREDENTIALS_URL, {"client_secret": "new-secret"}, format="json")

        assert response.status_code == 200
        connection.refresh_from_db()
        assert connection.get_credentials() == {
            "client_id": "original-id",
            "client_secret": "new-secret",
        }

    def test_requires_login(self, anon_api):
        response = anon_api.post(
            CREDENTIALS_URL,
            {"client_id": "id", "client_secret": "secret"},
            format="json",
        )

        assert response.status_code in (401, 403)
