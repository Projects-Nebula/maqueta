import httpx
import pytest

from apps.hotmart.client import (
    FakeHotmartClient,
    HotmartClientError,
    RealHotmartClient,
    build_hotmart_client,
)


def test_build_hotmart_client_returns_fake_when_credentials_none():
    client = build_hotmart_client(None)

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_fake_when_credentials_empty():
    client = build_hotmart_client({})

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_fake_when_only_client_id_set():
    client = build_hotmart_client({"client_id": "client-id", "client_secret": ""})

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_fake_when_only_client_secret_set():
    client = build_hotmart_client({"client_id": "", "client_secret": "client-secret"})

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_real_when_credentials_complete():
    client = build_hotmart_client({"client_id": "client-id", "client_secret": "client-secret"})

    assert isinstance(client, RealHotmartClient)


def test_fake_client_fetch_token_returns_token_bundle():
    client = FakeHotmartClient()

    bundle = client.fetch_token()

    assert bundle.access_token
    assert bundle.expires_in > 0


def test_fake_client_list_products_returns_products():
    client = FakeHotmartClient()

    products = client.list_products("some-access-token")

    assert isinstance(products, list)


class TestRealHotmartClientFetchToken:
    def _client(self):
        return RealHotmartClient(
            client_id="client-id",
            client_secret="client-secret",
            auth_base_url="https://auth.example.com/oauth",
            api_base_url="https://api.example.com",
            timeout=5,
        )

    def test_fetch_token_sends_client_credentials_grant_with_basic_auth(self, monkeypatch):
        captured = {}

        def _fake_post(url, *, data, auth, timeout):
            captured["url"] = url
            captured["data"] = data
            captured["auth"] = auth
            request = httpx.Request("POST", url)
            return httpx.Response(
                200, json={"access_token": "tok-123", "expires_in": 3600}, request=request
            )

        monkeypatch.setattr("httpx.post", _fake_post)

        bundle = self._client().fetch_token()

        assert bundle.access_token == "tok-123"
        assert bundle.expires_in == 3600
        assert captured["url"] == "https://auth.example.com/oauth/token"
        assert captured["data"]["grant_type"] == "client_credentials"
        assert captured["data"]["client_id"] == "client-id"
        assert captured["data"]["client_secret"] == "client-secret"
        assert captured["auth"] == ("client-id", "client-secret")

    def test_fetch_token_raises_hotmart_client_error_on_http_error(self, monkeypatch):
        def _fake_post(url, *, data, auth, timeout):
            request = httpx.Request("POST", url)
            response = httpx.Response(401, json={"error": "invalid_client"}, request=request)
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

        monkeypatch.setattr("httpx.post", _fake_post)

        with pytest.raises(HotmartClientError):
            self._client().fetch_token()

    def test_fetch_token_raises_on_unexpected_payload_shape(self, monkeypatch):
        def _fake_post(url, *, data, auth, timeout):
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"unexpected": "shape"}, request=request)

        monkeypatch.setattr("httpx.post", _fake_post)

        with pytest.raises(HotmartClientError):
            self._client().fetch_token()
