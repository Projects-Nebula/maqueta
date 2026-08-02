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
    """Raised when a stored refresh token is missing or Hotmart rejects
    it. Callers surface this as "reconnect required" (HTTP 409), never a
    500 — same tradeoff as `CredentialDecryptionError` in crypto.py."""


def ensure_fresh_token(connection: HotmartConnection, client: HotmartClient) -> str:
    """Returns a valid access token for `connection`, transparently
    refreshing it first if expired (spec: "Transparent Token Refresh").
    Never returns an empty string — raises HotmartReconnectRequired
    instead, so callers can't accidentally send an empty Bearer token
    upstream."""
    if not connection.is_expired:
        access_token = connection.get_access_token()
        if access_token:
            return access_token

    refresh_token = connection.get_refresh_token()
    if not refresh_token:
        raise HotmartReconnectRequired("no refresh token stored")

    try:
        tokens = client.refresh(refresh_token)
    except HotmartClientError as exc:
        raise HotmartReconnectRequired(str(exc)) from exc

    connection.set_tokens(
        access=tokens.access_token,
        refresh=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )
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
