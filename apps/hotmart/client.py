"""Hotmart HTTP client seam (see openspec design:
hotmart-developer-credentials-pivot).

Every Hotmart HTTP call goes through this module — parsing is confined
here, no other module sees raw Hotmart JSON. `build_hotmart_client()`
mirrors `apps/storefront/payments.py`'s `build_payment_provider`: it takes
a per-seller credentials dict (from `HotmartConnection.get_credentials()`),
never reads platform-level settings. An incomplete credential pair is
treated exactly like no credentials at all — never a real client with
partial config.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from django.conf import settings


class HotmartClientError(Exception):
    """Raised for any non-2xx response, timeout, or unexpected payload
    shape from Hotmart. Callers never see raw upstream JSON."""


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    expires_in: int


@dataclass(frozen=True)
class HotmartProduct:
    id: str
    name: str
    is_active: bool
    checkout_url: str


class HotmartClient(ABC):
    @abstractmethod
    def fetch_token(self) -> TokenBundle: ...

    @abstractmethod
    def list_products(self, access_token: str) -> list[HotmartProduct]: ...


class RealHotmartClient(HotmartClient):
    """Talks to the real Hotmart API via httpx. Base URLs come from
    settings (not hardcoded) so a documented-vs-actual endpoint drift is a
    config fix, not a code change. Every request carries an explicit
    timeout."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        auth_base_url: str,
        api_base_url: str,
        timeout: float,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_base_url = auth_base_url.rstrip("/")
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout = timeout

    def fetch_token(self) -> TokenBundle:
        """`client_credentials` grant — Basic auth AND client_id/secret in
        the body (open question in design.md: Hotmart's docs/screenshots
        suggest Basic auth; sending both keeps this tolerant of either
        contract without a second code path)."""
        return self._token_request(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        )

    def _token_request(self, data: dict) -> TokenBundle:
        try:
            response = httpx.post(
                f"{self._auth_base_url}/token",
                data=data,
                auth=(self._client_id, self._client_secret),
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return TokenBundle(
                access_token=payload["access_token"],
                expires_in=int(payload["expires_in"]),
            )
        except httpx.HTTPError as exc:
            raise HotmartClientError(f"hotmart token request failed: {exc}") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise HotmartClientError("hotmart token response had an unexpected shape") from exc

    def list_products(self, access_token: str) -> list[HotmartProduct]:
        try:
            response = httpx.get(
                f"{self._api_base_url}/products",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload["items"] if isinstance(payload, dict) else payload
            return [
                HotmartProduct(
                    id=str(item["id"]),
                    name=item.get("name", ""),
                    # Hotmart's real /products payload has no `is_active`
                    # boolean — only a `status` string (confirmed live:
                    # "ACTIVE" for a published product, "DRAFT" /
                    # "CHANGES_PENDING_ON_PRODUCT" otherwise).
                    is_active=item.get("status") == "ACTIVE",
                    # Real payload also has no `checkout_url` — left empty
                    # until the actual sales-link source is confirmed.
                    checkout_url=item.get("checkout_url", ""),
                )
                for item in items
            ]
        except httpx.HTTPError as exc:
            raise HotmartClientError(f"hotmart product list request failed: {exc}") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise HotmartClientError("hotmart product response had an unexpected shape") from exc


class FakeHotmartClient(HotmartClient):
    """Offline stand-in used whenever a connection's stored credentials are
    absent or incomplete — same role as apps.storefront.payments' Fake*
    providers. Lets the entire test suite (and local dev) run green with
    zero Hotmart credentials."""

    def fetch_token(self) -> TokenBundle:
        return TokenBundle(
            access_token=f"fake-access-{uuid.uuid4().hex}",
            expires_in=3600,
        )

    def list_products(self, access_token: str) -> list[HotmartProduct]:
        return [
            HotmartProduct(
                id="fake-product-1",
                name="Fake Product",
                is_active=True,
                checkout_url="https://example.com/checkout/fake-product-1",
            )
        ]


def build_hotmart_client(credentials: dict | None) -> HotmartClient:
    """`credentials` (a seller's decrypted `HotmartConnection.get_credentials()`
    dict, or None/empty) both client_id/client_secret set -> RealHotmartClient,
    otherwise FakeHotmartClient. Never a real client with partial
    credentials — an incomplete config is exactly as "not configured" as no
    config at all (same contract as build_payment_provider)."""
    client_id = (credentials or {}).get("client_id", "")
    client_secret = (credentials or {}).get("client_secret", "")
    if client_id and client_secret:
        return RealHotmartClient(
            client_id=client_id,
            client_secret=client_secret,
            auth_base_url=settings.HOTMART_AUTH_BASE_URL,
            api_base_url=settings.HOTMART_API_BASE_URL,
            timeout=settings.HOTMART_REQUEST_TIMEOUT,
        )
    return FakeHotmartClient()
