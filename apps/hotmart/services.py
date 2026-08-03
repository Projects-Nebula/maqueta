"""Hotmart business logic that sits between the HTTP layer and `client.py`
(see openspec design: hotmart-oauth-connect, "Data Flow" and "sync = shared
reconcile function, two triggers" decisions).

`ensure_fresh_token` and `reconcile_products` are called from both the
authenticated product-list endpoint (opportunistic sync on page load) and
the `sync_hotmart_connections` management command (cron for sellers who
never log in) — the same reconciliation logic runs either way.
"""

from __future__ import annotations

from .client import HotmartClient, HotmartClientError, HotmartProduct
from .models import HotmartConnection, HotmartProductLink


class HotmartReconnectRequired(Exception):
    """Raised when a connection has no stored credentials or Hotmart
    rejects a re-exchange attempt. Callers surface this as "reconnect
    required" (HTTP 409), never a 500 — same tradeoff as
    `CredentialDecryptionError` in crypto.py."""


def ensure_fresh_token(connection: HotmartConnection, client: HotmartClient) -> str:
    """Returns a valid access token for `connection`, transparently
    re-exchanging it first if expired (spec: "Token Re-Exchange on Expiry
    (No Refresh Token)"). `client_credentials` grants never return a
    refresh token, so re-exchange needs no user interaction — reconnect is
    only raised when credentials are absent or Hotmart rejects them. Never
    returns an empty string — raises HotmartReconnectRequired instead, so
    callers can't accidentally send an empty Bearer token upstream."""
    if not connection.is_expired:
        access_token = connection.get_access_token()
        if access_token:
            return access_token

    if not connection.has_credentials():
        raise HotmartReconnectRequired("no credentials stored")

    try:
        tokens = client.fetch_token()
    except HotmartClientError as exc:
        raise HotmartReconnectRequired(str(exc)) from exc

    connection.set_tokens(access=tokens.access_token, expires_in=tokens.expires_in)
    connection.save()
    return connection.get_access_token()


def reconcile_products(
    connection: HotmartConnection, products: list[HotmartProduct] | None
) -> None:
    """Fail-SAFE reconciliation (design ADR): `products=None` means the
    upstream fetch itself failed (timeout/5xx/parse error) — every link
    and landing is left exactly as-is. Only a SUCCESSFUL fetch (possibly
    an empty list) can trigger an unpublish, and only for links whose
    product is missing from that fetch or explicitly inactive. Already
    `UPSTREAM_MISSING` links are left alone (idempotent — re-publishing is
    an explicit owner action, never automatic)."""
    if products is None:
        return

    active_upstream_ids = {product.id for product in products if product.is_active}
    links = connection.product_links.filter(status=HotmartProductLink.Status.ACTIVE)
    for link in links:
        if link.hotmart_product_id not in active_upstream_ids:
            link.mark_missing()
            link.user_template.unpublish()
