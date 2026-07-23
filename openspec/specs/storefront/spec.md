# Capability: storefront

Lets a template owner publish products for sale and get paid through any of
several payment gateways, with a permanent purchase record independent of any
one gateway's own dashboard. Code: `apps/storefront/`, `templates/storefront/`,
`static/storefront/`.

## Requirement: Products
An authenticated owner SHALL manage `Product`s (name, description,
`price_cents` — always an integer minor-unit amount, never a float — optional
image from their own uploads, optional downloadable `digital_file`,
`is_active`) via `GET /productos/` + `ProductViewSet` (`/api/products/`,
owner-scoped, no IDOR).

#### Scenario: Only the owner's own products are ever visible or editable
- WHEN a user calls `/api/products/`
- THEN only `Product` rows they own are returned; PATCH/DELETE on another
  owner's product 404s via owner-scoped `get_queryset`

## Requirement: Publishing a template makes its products reachable
A `UserTemplate`'s public page (`GET /t/<slug>/`, editor capability) can embed
a product's buy button. The button/card references the product by id only —
the public page renderer never re-validates ownership per view (that
enforcement lives in checkout), matching how any other embedded content on a
published page works.

## Requirement: Multi-gateway payment providers
The system SHALL support checkout through any of Stripe, Mercado Pago,
PayPal, Braintree, Wompi, PayU, ePayco, or Bold, chosen by the BUYER at
checkout time — never a single global "active gateway" setting. Each gateway
has a real implementation and a `Fake*` implementation
(`apps/storefront/payments.py`, `PaymentProvider` ABC); a gateway that is
enabled without complete real credentials silently runs its `Fake*` variant
(deterministic, no network) instead of failing.

#### Scenario: Fake gateway completes a purchase without any real credentials
- WHEN a seller enables a gateway with no credentials configured
- AND a buyer completes checkout for that gateway
- THEN a `FakeXProvider` session is created, marked paid instantly, and an
  `Order` is recorded immediately by `CheckoutView` (see the next
  requirement) — the buyer reaches the success page, never a stuck
  "Procesando tu pago..." screen

## Requirement: Per-owner gateway configuration
Payment credentials are configured per SELLER, not globally — this is a
multi-tenant editor (`/productos/` is already owner-scoped; gateway
credentials must be too). `PaymentGatewayConfig` (owner, gateway, `is_enabled`,
encrypted credentials blob) is managed by the owner at `GET /config/` +
`PaymentGatewayConfigViewSet` (`/api/payment-gateway-configs/`).
Credentials are encrypted at rest (`apps/storefront/crypto.py`, Fernet keyed
from `DJANGO_SECRET_KEY`) and are WRITE-ONLY in every API response — never
returned, even to the owner who set them; only a per-field
presence boolean (`has_credentials`) is exposed.

#### Scenario: A disabled or unconfigured gateway is not reachable at all
- WHEN a seller has never created a `PaymentGatewayConfig` row for a gateway,
  or has one with `is_enabled=False`
- THEN `POST /comprar/<product_id>/<gateway>/` 404s for that product+gateway
  pair — never offer a checkout path the seller didn't turn on

#### Scenario: Credentials are never leaked back
- WHEN an owner fetches their own `/api/payment-gateway-configs/`
- THEN the response never includes credential values, regardless of
  authentication — only `has_credentials` (booleans) and `required_fields`

## Requirement: Checkout never trusts the client for money
`POST /comprar/<product_id>/<gateway>/` SHALL always re-read
`Product.price_cents` from the database — never a price/currency/amount from
the request body. `authentication_classes = []` on this view (and every
gateway's webhook view): DRF's `SessionAuthentication` runs its own CSRF
check independent of `@csrf_exempt` whenever it authenticates a request via
session, which would otherwise 403 a logged-in buyer (e.g. the product
owner testing their own button) with no real security benefit, since the
view is `AllowAny` and was never meant to authenticate the requester at all.

#### Scenario: Client-supplied price is ignored
- WHEN a POST body includes a different amount than the product's real price
- THEN the created checkout session still charges `Product.price_cents`

#### Scenario: A logged-in session can still check out without a CSRF header
- WHEN a logged-in user (e.g. a template owner) POSTs to their own product's
  checkout URL with no `X-CSRFToken` header
- THEN the request succeeds (302 redirect), not a CSRF 403

## Requirement: Legacy checkout URL and gateway-less delivery
`POST /comprar/<product_id>/` (no gateway segment — the shape baked into
any `UserTemplate` state saved before multi-gateway checkout shipped) SHALL
NOT 404 a buy button that already worked before. It falls back to the
seller's first enabled gateway (deterministic alphabetical order). If the
seller has NO gateway enabled at all, the product is delivered directly and
a real, permanent `Order` is still recorded (`gateway="none"`,
`amount_cents=0`, `status=PAID`) — a $0 delivery is auditable exactly like
a real purchase, never silently untracked.

#### Scenario: Legacy URL uses the seller's first enabled gateway
- WHEN a buyer POSTs `/comprar/<id>/` (no gateway) and the seller has one or
  more gateways enabled
- THEN checkout proceeds via the alphabetically-first enabled gateway

#### Scenario: No gateway enabled at all delivers for free, still tracked
- WHEN a buyer POSTs a checkout URL (legacy or otherwise resolving to no
  enabled gateway) and the seller has zero enabled `PaymentGatewayConfig`
  rows
- THEN the buyer reaches the success page immediately and an `Order` with
  `gateway="none"`/`amount_cents=0`/`status=PAID` exists for that product

## Requirement: An Order is the permanent, gateway-independent purchase record
`Order` (product, `gateway`, `gateway_session_id` — unique per gateway, not
globally, since two different gateways could theoretically collide on
session-id strings — buyer email, amount, currency, status) SHALL be created
ONLY by a gateway's signature-verified webhook view for a REAL provider.
`GatewayWebhookView` (base for all 8 gateway webhook views) tries every
enabled `PaymentGatewayConfig` for that gateway across all owners until one's
credentials successfully verify the inbound signature — a webhook payload
carries no explicit "which seller" identity of its own.

#### Scenario: Fake-provider checkout is the one narrow exception
- WHEN `CheckoutView` used a `Fake*` provider for this checkout (no real
  credentials configured)
- THEN it records the Order directly, right after creating the session —
  there is no real gateway server in dev/test to ever deliver a webhook

#### Scenario: An unverifiable webhook is rejected, not silently accepted
- WHEN no enabled seller's credentials for a gateway successfully verify an
  inbound webhook's signature
- THEN the webhook view responds 400 and no `Order` is created or modified

## Requirement: Digital downloads are gated, not static files
When `Product.digital_file` is set, a paid `Order` gets a `download_token`
(minted only once payment is confirmed) and a `max_downloads` cap.
`GET /descargas/<token>/` (editor capability's 404-enumeration posture
mirrored here) 404s identically for a wrong token, unpaid order, no digital
file, or exhausted download count.

#### Scenario: Download count is enforced
- WHEN a valid token's order has already reached `max_downloads`
- THEN the next download attempt 404s instead of serving the file again

## Requirement: The success page tolerates webhook delivery lag
`GET /gracias/?gateway=<gw>&session_id=<id>` SHALL NOT assume the `Order`
already exists — the webhook is asynchronous and may not have landed yet.
It falls back to a direct `PaymentProvider.retrieve_session` lookup, but
NEVER fabricates an `Order` itself even if the provider reports "paid" —
only the webhook (or the fake-provider exception above) may create one.

#### Scenario: Race condition shows "pending", not a false positive
- WHEN a buyer reaches the success page before the webhook has landed
- THEN the page reports "pending" rather than claiming a download is ready
  for an `Order` that doesn't exist in this database yet
