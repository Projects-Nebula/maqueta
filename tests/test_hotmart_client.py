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


def test_fake_client_list_products_returns_non_empty_ucode():
    client = FakeHotmartClient()

    products = client.list_products("some-access-token")

    assert products[0].ucode


def test_fake_client_list_offers_returns_offers():
    client = FakeHotmartClient()

    offers = client.list_offers("some-access-token", "fake-ucode-1")

    assert isinstance(offers, list)
    assert offers[0].price


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


class TestRealHotmartClientListProducts:
    def _client(self):
        return RealHotmartClient(
            client_id="client-id",
            client_secret="client-secret",
            auth_base_url="https://auth.example.com/oauth",
            api_base_url="https://api.example.com",
            timeout=5,
        )

    def test_list_products_maps_active_status_not_missing_is_active_field(self, monkeypatch):
        """Hotmart's real /products payload has no `is_active` boolean —
        only a `status` string. Regression test for a bug where
        `item.get("is_active", False)` silently defaulted every real
        product to inactive, which made reconcile_products() unpublish
        every linked landing on every sync run."""

        def _fake_get(url, *, headers, timeout):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": 1, "name": "Live", "status": "ACTIVE"},
                        {"id": 2, "name": "Draft", "status": "DRAFT"},
                    ]
                },
                request=request,
            )

        monkeypatch.setattr("httpx.get", _fake_get)

        products = self._client().list_products("some-access-token")

        assert products[0].id == "1"
        assert products[0].is_active is True
        assert products[1].id == "2"
        assert products[1].is_active is False

    def test_list_products_maps_ucode(self, monkeypatch):
        def _fake_get(url, *, headers, timeout):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": 1, "ucode": "abc-123", "name": "Live", "status": "ACTIVE"},
                    ]
                },
                request=request,
            )

        monkeypatch.setattr("httpx.get", _fake_get)

        products = self._client().list_products("some-access-token")

        assert products[0].ucode == "abc-123"


class TestRealHotmartClientListOffers:
    def _client(self):
        return RealHotmartClient(
            client_id="client-id",
            client_secret="client-secret",
            auth_base_url="https://auth.example.com/oauth",
            api_base_url="https://api.example.com",
            timeout=5,
        )

    def test_list_offers_requests_the_product_offers_endpoint(self, monkeypatch):
        captured = {}

        def _fake_get(url, *, headers, timeout):
            captured["url"] = url
            captured["headers"] = headers
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "offer-1", "price": "97.00", "currency": "USD", "description": ""},
                    ]
                },
                request=request,
            )

        monkeypatch.setattr("httpx.get", _fake_get)

        offers = self._client().list_offers("some-access-token", "abc-123")

        assert captured["url"] == "https://api.example.com/products/abc-123/offers"
        assert captured["headers"]["Authorization"] == "Bearer some-access-token"
        assert offers[0].id == "offer-1"
        assert offers[0].price == "97.00"
        assert offers[0].currency == "USD"
        assert offers[0].description == ""

    def test_list_offers_tolerates_missing_fields(self, monkeypatch):
        """Real field names beyond what was live-tested for /products are
        unconfirmed for /offers — tolerate a payload missing price/currency/
        description rather than raising."""

        def _fake_get(url, *, headers, timeout):
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"items": [{"id": "offer-1"}]}, request=request)

        monkeypatch.setattr("httpx.get", _fake_get)

        offers = self._client().list_offers("some-access-token", "abc-123")

        assert offers[0].id == "offer-1"
        assert offers[0].price == ""
        assert offers[0].currency == ""
        assert offers[0].description == ""

    def test_list_offers_raises_hotmart_client_error_on_http_error(self, monkeypatch):
        def _fake_get(url, *, headers, timeout):
            request = httpx.Request("GET", url)
            response = httpx.Response(404, json={"error": "not_found"}, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)

        monkeypatch.setattr("httpx.get", _fake_get)

        with pytest.raises(HotmartClientError):
            self._client().list_offers("some-access-token", "abc-123")

    def test_list_offers_raises_on_unexpected_payload_shape(self, monkeypatch):
        def _fake_get(url, *, headers, timeout):
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"unexpected": "shape"}, request=request)

        monkeypatch.setattr("httpx.get", _fake_get)

        with pytest.raises(HotmartClientError):
            self._client().list_offers("some-access-token", "abc-123")
