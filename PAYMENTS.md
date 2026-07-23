# PAYMENTS.md — Multi-gateway checkout (Mercado Pago, Stripe, Wompi, PayPal, Braintree, PayU, ePayco, Bold)

Execution plan for an agent to implement end-to-end, phase by phase, without
stopping until done. Mirrors the structure/discipline of the earlier
`REFACTOR.md`/`FEATURE.md` plans this project already executed (see git log
and `CHANGELOG.md`/`BACKLOG.csv` for how those closed out) — same rule
applies: **update `BACKLOG.csv`/`CHANGELOG.md`/`learnings.jsonl` when done,
then delete this file** (Section 9).

## 0. Decision already made (do not re-litigate)

The buyer picks the gateway **at checkout**, not the shop owner ahead of
time. A product's buy button becomes N buttons — one per gateway that has
real (or fake, in dev) credentials configured — instead of one "Comprar"
form. All 5 gateways can be live simultaneously; each has its own webhook
endpoint, since each provider's webhook payload/signature scheme is
completely different from the others (verified below) and must not be
merged into one shared endpoint.

**Cannot be done for you**: creating the actual developer/sandbox accounts
on each platform (Mercado Pago, Stripe, PayPal, Braintree, Wompi, PayU,
ePayco, Bold) — that requires the project owner's own signup/business
info. This plan produces the *code* and tells you exactly which env vars
to fill in and where each platform's docs are; getting the actual sandbox
keys is a manual step for whoever runs this, not something an agent can
automate.

**Research honesty note**: sections 2.1–2.5 (Stripe/Mercado Pago/PayPal/
Braintree/Wompi) were checked against each platform's own docs during this
planning pass (still flagged where the exact field order wasn't fully
confirmable). Sections 2.6–2.8 (PayU/ePayco/Bold) below are lower
confidence — ePayco's and Bold's own doc sites did not return usable
content through this session's fetch tool (ePayco: connection refused;
Bold: JS-rendered docs, only nav chrome came back), so those two rely on
general/training knowledge of each platform's well-known public
integration pattern rather than a freshly re-confirmed source. **Do not
implement PayU/ePayco/Bold signature verification from this document
alone** — re-fetch each platform's current docs (or find their official
SDK, if one exists) at implementation time; this is a security-critical
step (a forged webhook could fabricate a paid `Order`) and deserves a live
check, not a paraphrase from a planning pass.

## 1. Architecture

### 1.1 `PaymentProvider` ABC — unchanged shape, new instances

`apps/storefront/payments.py` already has the right abstraction
(`create_checkout_session`, `retrieve_session`, `parse_webhook_event`). Keep
it exactly as-is; add one concrete class per gateway plus **one Fake
variant per gateway** (not a single shared `FakePaymentProvider` anymore —
each gateway needs its own fake so the buyer can click "Pagar con Wompi" in
dev without Stripe/PayPal/etc keys being configured too).

```python
GATEWAY_CHOICES = [
    "stripe", "mercadopago", "paypal", "braintree", "wompi",
    "payu", "epayco", "bold",
]

def build_payment_provider(settings, gateway: str) -> PaymentProvider:
    """One instance per gateway, real-or-fake independently based on
    whether THAT gateway's own credentials are configured — never a single
    global PAYMENT_PROVIDER switch anymore."""
```

Replace the current single `build_payment_provider(settings)` (no gateway
arg) with the signature above. `apps/ai_assistant`/anything unrelated to
storefront is untouched — this is a `payments.py`/`views.py` change only.

Add a small registry so views don't hardcode a big if/elif:

```python
_PROVIDERS = {
    "stripe": (StripePaymentProvider, FakeStripeProvider, "STRIPE_SECRET_KEY"),
    "mercadopago": (MercadoPagoPaymentProvider, FakeMercadoPagoProvider, "MERCADOPAGO_ACCESS_TOKEN"),
    "paypal": (PayPalPaymentProvider, FakePayPalProvider, "PAYPAL_CLIENT_SECRET"),
    "braintree": (BraintreePaymentProvider, FakeBraintreeProvider, "BRAINTREE_PRIVATE_KEY"),
    "wompi": (WompiPaymentProvider, FakeWompiProvider, "WOMPI_PRIVATE_KEY"),
    "payu": (PayUPaymentProvider, FakePayUProvider, "PAYU_API_KEY"),
    "epayco": (EpaycoPaymentProvider, FakeEpaycoProvider, "EPAYCO_P_KEY"),
    "bold": (BoldPaymentProvider, FakeBoldProvider, "BOLD_SECRET_KEY"),
}

def enabled_gateways(settings) -> list[str]:
    """Every gateway in GATEWAY_CHOICES is always 'enabled' (fake fallback),
    used to render one button per gateway on the product card."""
    return list(_PROVIDERS)

def build_payment_provider(settings, gateway: str) -> PaymentProvider:
    real_cls, fake_cls, key_setting = _PROVIDERS[gateway]
    if getattr(settings, key_setting, ""):
        return real_cls(settings)
    return fake_cls()
```

Every button is always shown (fake mode "just works" for demoing all 5
without any real keys) — real credentials silently upgrade that one
gateway from fake to live. Do not hide a gateway's button just because it's
unconfigured; that would make local dev/demo confusing about what exists.

### 1.2 `Order` model migration

`stripe_session_id` (globally unique) becomes gateway-scoped — two
different gateways could theoretically mint colliding session id strings,
and the field name itself is now wrong for 4 of the 5 gateways.

```python
class Order(models.Model):
    class Gateway(models.TextChoices):
        STRIPE = "stripe"
        MERCADOPAGO = "mercadopago"
        PAYPAL = "paypal"
        BRAINTREE = "braintree"
        WOMPI = "wompi"

    gateway = models.CharField(max_length=16, choices=Gateway.choices)
    gateway_session_id = models.CharField(max_length=255)
    # ... rest unchanged (product, buyer_email, amount_cents, currency, status, download_*)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("gateway", "gateway_session_id")]
```

Write a real Django migration renaming `stripe_session_id` ->
`gateway_session_id`, adding `gateway` with a one-time `RunPython` data
migration defaulting existing rows to `Order.Gateway.STRIPE` (every
existing `Order` row was necessarily created via Stripe, since that's the
only gateway that existed before this plan). Update every reference
(`apps/storefront/views.py`, `admin.py`, all of `tests/test_checkout.py`,
`tests/test_stripe_webhook.py`, `tests/test_digital_downloads.py`) to the
new field name.

### 1.3 URLs — one webhook per gateway, checkout takes a gateway segment

```python
urlpatterns = [
    path("productos/", products_view, name="products"),
    path("comprar/<int:product_id>/<str:gateway>/", CheckoutView.as_view(), name="checkout"),
    path("gracias/", SuccessView.as_view(), name="success"),
    path("cancelado/", checkout_cancel_view, name="checkout-cancel"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="webhook-stripe"),
    path("webhooks/mercadopago/", MercadoPagoWebhookView.as_view(), name="webhook-mercadopago"),
    path("webhooks/paypal/", PayPalWebhookView.as_view(), name="webhook-paypal"),
    path("webhooks/braintree/", BraintreeWebhookView.as_view(), name="webhook-braintree"),
    path("webhooks/wompi/", WompiWebhookView.as_view(), name="webhook-wompi"),
    path("webhooks/payu/", PayUWebhookView.as_view(), name="webhook-payu"),
    path("webhooks/epayco/", EpaycoWebhookView.as_view(), name="webhook-epayco"),
    path("webhooks/bold/", BoldWebhookView.as_view(), name="webhook-bold"),
    path("descargas/<str:token>/", DownloadView.as_view(), name="download"),
]
```

`CheckoutView.post` validates `gateway` against `_PROVIDERS` (404 on an
unknown gateway string — same "never let it be enumerable/guessable"
posture as the rest of this app) instead of hardcoding Stripe.
`_record_order_for_session` (already shared/de-duplicated this session)
gains a `gateway` parameter and is called by all 5 webhook views plus the
fake-provider-immediate-record path in `CheckoutView`, exactly like it
already works for Stripe today — do not re-invent that part, only
parameterize it.

## 2. Per-gateway integration notes (verified against each platform's own
docs where fetchable — flagged where a live doc lookup during
implementation is still required before trusting an exact field/header
name)

### 2.1 Stripe (already implemented — reference pattern for the other 4)

No functional change beyond parameterizing by `gateway`. Continue using the
official `stripe` Python package, `stripe.checkout.Session.create`,
`stripe.Webhook.construct_event`.

### 2.2 Mercado Pago

- Official Python SDK: `mercadopago` (PyPI `mercadopago`). Use
  `sdk.preference().create({...})` (Checkout Pro) to get an `init_point`
  (sandbox: `sandbox_init_point`) — redirect the buyer there, mirroring
  Stripe's `session.url` pattern (`CheckoutSession(id=preference_id,
  url=init_point)`).
- Credentials: `MERCADOPAGO_ACCESS_TOKEN` (test tokens are prefixed
  `TEST-`, obtained from the "Tus integraciones" dashboard, Test/Sandbox
  credentials tab — this is the manual step the project owner must do).
- **Webhook** (`/webhooks/mercadopago/`): verified live against MP's own
  docs — signature arrives via `x-signature` header, format
  `ts=<timestamp>,v1=<hmac-hex>`, plus an `x-request-id` header, HMAC-**SHA256**
  keyed by a per-integration webhook secret (separate from the access
  token, generated in the same dashboard). The exact manifest string that
  gets signed (order/format of `id`/`request-id`/`ts` before hashing) was
  **not fully confirmed** from the fetched docs during this planning pass
  — before writing `MercadoPagoPaymentProvider.parse_webhook_event`,
  re-check `https://www.mercadopago.com.ar/developers/en/docs/your-integrations/notifications/webhooks`
  (or the official SDK's own webhook-validation helper, if it exposes one —
  prefer that over hand-rolling the HMAC) rather than trusting this
  document's paraphrase. Payload shape: `{"type": "payment", "data": {"id":
  "<payment_id>"}, ...}` — `type` distinguishes payment vs other event
  kinds (only handle `type == "payment"`, mirroring Stripe's
  `event_type != "checkout.session.completed"` early-return). Must respond
  200/201 within ~22s or MP retries — same "never rate-limit the webhook"
  posture already established for `StripeWebhookView`.

### 2.3 PayPal

- Official SDK: `paypal-server-sdk` (or `checkout-server-sdk`, PayPal's
  current officially-maintained package — confirm the current package name
  at implementation time, PayPal has renamed/consolidated its SDKs more
  than once). Orders API v2 (`/v2/checkout/orders`) — `intent: CAPTURE`,
  redirect the buyer to the returned `approve` link (same
  `CheckoutSession(id=order_id, url=approve_link)` shape).
- Credentials: `PAYPAL_CLIENT_ID` + `PAYPAL_CLIENT_SECRET`, sandbox app
  created at developer.paypal.com — sandbox and live use different base
  URLs (`api-m.sandbox.paypal.com` vs `api-m.paypal.com`).
- **Webhook** (`/webhooks/paypal/`): verification is a server-to-server API
  call, NOT a local HMAC check like the other four — POST the transmission
  headers (`PAYPAL-TRANSMISSION-ID`, `PAYPAL-TRANSMISSION-TIME`,
  `PAYPAL-CERT-URL`, `PAYPAL-AUTH-ALGO`, `PAYPAL-TRANSMISSION-SIG`) plus
  your `webhook_id` and the raw event body to PayPal's own
  `verify-webhook-signature` endpoint; trust the event only if that call
  itself returns `SUCCESS`. This is architecturally different from the
  other 4 gateways' `parse_webhook_event` (which are all local/offline
  crypto checks) — `PayPalPaymentProvider.parse_webhook_event` will need to
  make an outbound HTTPS call, which the existing
  `FakePaymentProvider`/other fakes never do; keep
  `FakePayPalProvider.parse_webhook_event` purely local (no network) same
  as every other fake in this project, per this session's own tests-must-
  never-hit-a-real-API convention.

### 2.4 Braintree

- Official SDK: `braintree` (PyPI). Simplest of the 5 to integrate:
  `gateway.transaction.sale({...})` for a direct charge, or
  `gateway.client_token.generate()` + Drop-in UI for a hosted flow closer
  to the other gateways' "redirect to their page" pattern — **pick the
  redirect/hosted flow** for consistency with the other 4's
  `CheckoutSession.url` contract (Braintree's own hosted checkout page, not
  Drop-in embedded in our own page — that would be architecturally
  inconsistent with everything else in this plan and a bigger frontend
  change than scoped here).
- Credentials: `BRAINTREE_MERCHANT_ID` + `BRAINTREE_PUBLIC_KEY` +
  `BRAINTREE_PRIVATE_KEY`, sandbox account at braintreegateway.com.
- **Webhook** (`/webhooks/braintree/`): the SDK handles verification
  itself — `gateway.webhook_notification.parse(bt_signature, bt_payload)`
  raises on an invalid signature and returns a parsed notification object
  on success (`notification.kind`,
  `notification.transaction.id`/`.status`). Do not hand-roll HMAC here;
  this is the one gateway whose SDK makes `parse_webhook_event` a thin
  wrapper.

### 2.5 Wompi (Colombia — no official Python SDK)

- No first-party Python SDK exists; integrate directly against Wompi's
  REST API via `requests` (mirrors how this project already avoids adding
  a dependency for something a few HTTP calls can do — see `ponytail`
  guidance in `AGENTS.md`). Sandbox base URL uses Wompi's own
  sandbox/`pruebas` credentials (public + private + integrity keys, from
  the Wompi merchant dashboard — again, a manual signup step).
- Checkout: Wompi's hosted "Web Checkout" widget/redirect flow — build the
  checkout URL/reference per their docs (a `reference` you generate,
  amount in cents, currency `COP`, and an **integrity signature** — a
  SHA256 hash of `reference + amount_in_cents + currency + integrity_secret`
  — computed before redirecting, separate from the webhook's own
  signature).
- **Webhook** (`/webhooks/wompi/`): event payload includes a
  `signature.checksum` field — verify by recomputing SHA256 over the
  documented ordered list of event properties + a timestamp + your events
  secret, and comparing. **Confirm the exact property list/order against
  Wompi's live "Eventos" documentation at implementation time** — this
  plan intentionally does not paraphrase an unconfirmed field order for a
  security-critical signature check; re-fetch
  `https://docs.wompi.co/docs/colombia/eventos/` (or the current
  equivalent URL) before writing `WompiPaymentProvider.parse_webhook_event`.

### 2.6 PayU (LatAm — WebCheckout)

- No modern official Python SDK maintained; integrate directly (a hidden
  HTML form auto-submitted via `HTTP POST` to PayU's WebCheckout URL —
  sandbox: `https://sandbox.checkout.payulatam.com/ppp-web-gateway-payu/`,
  same "own hosted page" pattern as the other gateways, so
  `CheckoutSession.url` here is a URL our own server generates — a tiny
  Django view rendering the auto-submit form — not a URL PayU's API
  returns, since WebCheckout is a client-side-POST integration, not a
  create-session API call like Stripe/Mercado Pago/PayPal).
- Required fields: `merchantId`, `accountId`, `referenceCode` (our own
  unique order reference, generate like `Order.generate_download_token()`
  does), `amount`, `currency` (`COP`), `signature`. **Signature**: MD5 of
  `ApiKey~merchantId~referenceCode~amount~currency` — confirmed shape from
  PayU's own docs during this planning pass; the amount's exact string
  formatting (PayU is known to require a fixed number of decimals, e.g.
  `"10.00"` not `"10"`) must be re-verified at implementation time, a
  well-known integration gotcha for this specific field.
- Credentials: `PAYU_MERCHANT_ID`, `PAYU_ACCOUNT_ID`, `PAYU_API_KEY`,
  `PAYU_API_LOGIN` — PayU's own test/sandbox merchant+account+key set
  (documented as fixed public sandbox values for early testing, real
  sandbox credentials from the merchant dashboard for anything further).
- **Webhook** (`/webhooks/payu/`, PayU calls this the "confirmation page"):
  POSTs transaction result fields including `reference_sale`,
  `value`, `currency`, `state_pol` (transaction status code), and its own
  `sign` field — verify by recomputing MD5 of
  `ApiKey~merchant_id~reference_sale~value~currency~state_pol` and
  comparing to the posted `sign`. Confirm this exact field list/order
  against PayU's live docs before implementing (this session's fetch
  confirmed the request-side signature formula but not the confirmation-
  page one in full detail).

### 2.7 ePayco (Colombia)

- Official SDK exists: `epayco-python` (PyPI, ePayco-maintained) — prefer
  it over hand-rolling requests if it's still maintained/importable at
  implementation time; confirm on PyPI first.
- Checkout: ePayco's "Checkout" is a client-side JS widget/redirect
  (`https://checkout.epayco.co`) keyed by a public key
  (`EPAYCO_PUBLIC_KEY`) — similar hosted-redirect shape to the others.
- Credentials: `EPAYCO_PUBLIC_KEY`, `EPAYCO_P_KEY` (private key),
  `EPAYCO_P_CUST_ID_CLIENTE` (customer/merchant id) — from the ePayco
  dashboard, which has an explicit sandbox/test mode toggle.
- **Webhook** (`/webhooks/epayco/`, ePayco calls this "confirmación de
  transacción"): POSTs `x_cust_id_cliente`, `x_ref_payco`,
  `x_transaction_id`, `x_amount`, `x_currency_code`, `x_signature` among
  other `x_*` fields — verified signature is SHA256 of
  `p_cust_id_cliente^p_key^x_ref_payco^x_transaction_id^x_amount^x_currency_code`
  (`^` literal separator) per ePayco's well-documented public pattern.
  **This session's own fetch of ePayco's docs failed (connection
  refused)** — this formula is from general knowledge, not a live-
  reconfirmed source; treat it as a strong starting guess, not ground
  truth, and verify against `docs.epayco.co` (or the `epayco-python` SDK's
  own source, if it exposes a verification helper) before trusting it in
  production.

### 2.8 Bold (Colombia)

- **Lowest-confidence gateway in this plan.** Bold's own docs site
  (`developers.bold.co`) is JS-rendered — this session's fetch only ever
  returned navigation chrome, never the actual field/signature
  specification, for the payment-button, manual-integration, and index
  pages alike. Do not start writing `BoldPaymentProvider` from this
  section — start by re-fetching (or asking a human to paste) the actual
  "Esquema de datos" and "Webhook" pages' content first; everything below
  is a best-effort placeholder from general knowledge of how Bold's button
  integration is commonly described, not a confirmed spec.
- Believed shape (**re-verify**): a "Botón de pagos" embed/link generated
  with `order-id`, `amount`, `currency` (`COP`), `description`, an API key,
  and an integrity signature/hash over those fields plus a secret —
  structurally similar to Wompi's integrity-signature pattern (same
  country, similar generation of merchants/integrators), which is at least
  a reasonable starting hypothesis but must not be trusted as-is.
- Credentials (names to confirm): likely `BOLD_API_KEY`/`BOLD_SECRET_KEY`
  from Bold's "Llaves de integración" dashboard page (this page title was
  visible in the fetched navigation, unlike the field/hash specifics).
- **Webhook** (`/webhooks/bold/`): unconfirmed shape/signature scheme —
  Bold's docs reference a dedicated "Webhook" page that this session could
  not extract content from. Treat `BoldPaymentProvider.parse_webhook_event`
  as the one provider in this whole plan that needs real documentation
  research (not just re-confirmation of a mostly-right guess) before any
  code is written.

## 3. Settings (`config/settings/base.py`)

Add, alongside the existing `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`
pattern (same `env(...)` posture — empty string default, never required):

```python
MERCADOPAGO_ACCESS_TOKEN=(str, ""),
MERCADOPAGO_WEBHOOK_SECRET=(str, ""),
PAYPAL_CLIENT_ID=(str, ""),
PAYPAL_CLIENT_SECRET=(str, ""),
PAYPAL_WEBHOOK_ID=(str, ""),
PAYPAL_ENV=(str, "sandbox"),  # "sandbox" | "live" — selects the API base URL
BRAINTREE_MERCHANT_ID=(str, ""),
BRAINTREE_PUBLIC_KEY=(str, ""),
BRAINTREE_PRIVATE_KEY=(str, ""),
BRAINTREE_ENV=(str, "sandbox"),
WOMPI_PUBLIC_KEY=(str, ""),
WOMPI_PRIVATE_KEY=(str, ""),
WOMPI_INTEGRITY_SECRET=(str, ""),
WOMPI_EVENTS_SECRET=(str, ""),
PAYU_MERCHANT_ID=(str, ""),
PAYU_ACCOUNT_ID=(str, ""),
PAYU_API_KEY=(str, ""),
PAYU_API_LOGIN=(str, ""),
EPAYCO_PUBLIC_KEY=(str, ""),
EPAYCO_P_KEY=(str, ""),
EPAYCO_P_CUST_ID_CLIENTE=(str, ""),
BOLD_API_KEY=(str, ""),   # names TBC — see 2.8, Bold's docs weren't fetchable this pass
BOLD_SECRET_KEY=(str, ""),
```

No single `PAYMENT_PROVIDER` setting anymore (each gateway is
independently real-or-fake per `build_payment_provider(settings,
gateway)`) — remove it and update every place that currently reads it.

## 4. Checkout UI

`apps/editor/rendering.py`'s `_render_node`/`public_page_html` need no
change (they render whatever's in `state`, agnostic to gateway count) —
this is a `static/editor/editor-core.js` (`productCardNode`-equivalent —
already routed through the AI this session, see `BACKLOG.csv` row 44) and
`apps/ai_assistant/prompts.py` change: the product-card spec the AI is
taught to generate needs N `<form>`s (one per gateway in
`enabled_gateways(settings)`, fed into `available_products`' context or a
new small `available_gateways` context list — mirror the existing
`available_products` server-populated pattern exactly, do not let the
client dictate which gateways exist), each `action="/comprar/<id>/<gateway>/"`
with a human label ("Pagar con Mercado Pago", "Pagar con PayPal", etc).

## 5. Fakes — one per gateway, offline, deterministic

Mirror `FakePaymentProvider`'s existing shape exactly (class-level
`_sessions` dict, `payment_status: "paid"` instantly, no network) for all 7
new providers (`FakeMercadoPagoProvider`/`FakePayPalProvider`/
`FakeBraintreeProvider`/`FakeWompiProvider`/`FakePayUProvider`/
`FakeEpaycoProvider`/`FakeBoldProvider`). Do not collapse them into one
shared fake class — each must independently satisfy its own gateway's
`CheckoutSession`/`SessionStatus` field shapes so a webhook/checkout test
for one gateway can never accidentally exercise another's code path.

## 6. Tests

For each gateway: mirror `tests/test_checkout.py` and
`tests/test_stripe_webhook.py`'s existing test shapes exactly (redirect
happy path, 404 for missing/inactive product, works anonymously, ignores
client-supplied price, the logged-in-session-without-CSRF-header
regression test, fake-provider-records-order-immediately regression test,
webhook idempotency, webhook invalid-signature rejection,
digital-download-token-on-paid-order). That is roughly 8-10 tests × 8
gateways — do not shortcut this; the checkout CSRF bug and the
fake-provider-stuck-forever bug (both fixed this session, see
`learnings.jsonl` ids `2026-07-23-11`/`2026-07-23-12`/`2026-07-23-13`) were
each invisible to a smaller test surface and each was a real, live-
reproduced bug. `PayPalPaymentProvider.parse_webhook_event`'s outbound
verification call must be mocked in its own real-provider signature test
(never hit PayPal's actual API from a test) — same posture as every other
"tests must never hit the real X API" rule already in `AGENTS.md`.

## 7. Docker/CI

No new system packages needed — all pure-Python:
`stripe`, `mercadopago`, `paypal-server-sdk` (or current name), `braintree`,
`epayco-python` (confirm still maintained on PyPI first, else `requests`
directly). Wompi/PayU/Bold need no SDK, just `requests` (already a
transitive dependency). Add whichever packages via `uv add`. No Dockerfile
changes expected — verify with a real `docker build` per this project's
own established discipline before considering this phase done.

## 8. Verification (do not skip — this project's own established discipline)

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `manage.py check`, `manage.py makemigrations --check` all green.
- Real Playwright run against a live `manage.py runserver`: create a
  product, view its public page, click through all 8 fake-mode "Pagar
  con..." buttons end to end to "¡Gracias por tu compra!" (mirrors exactly
  how this session verified the Stripe/fake checkout bugs live, not just
  via pytest).
- `docker build` after the Dockerfile/pyproject changes.
- Explicitly note in the close-out (Section 9) which of the 8 gateways'
  REAL sandbox credentials were actually available/tested in this
  environment vs. only verified through the fake provider — this project's
  own `BACKLOG.csv` row 41 already carries exactly this kind of honest
  caveat for Stripe (`stripe_test_mode_checkout_page_round_trip_not_verified`);
  do the same for whichever of the other 7 aren't actually configured with
  real test keys when this is executed. Bold and ePayco specifically
  **must not** be marked as fully implemented/verified if their webhook
  signature scheme was only ever the unconfirmed placeholder from Section
  2.7/2.8 — re-fetch their real docs before claiming those two done, not
  just before claiming them tested.

## 9. Close-out (same discipline as REFACTOR.md/FEATURE.md)

Once all phases are done and verified:

1. Add one `BACKLOG.csv` row (or one per gateway if that's clearer to
   filter on `area=storefront`) describing what was built, files touched,
   verification performed, and `blocked_by` for any gateway whose real
   sandbox credentials weren't available to test live.
2. Add a `CHANGELOG.md` `### Added` entry in the same voice/detail level as
   the existing "Public template publishing + storefront" entry.
3. Append one `learnings.jsonl` line per genuinely new, verified gotcha
   found during implementation (e.g. whatever the real Mercado Pago
   manifest-string/Wompi checksum field order actually turns out to be,
   once confirmed against live docs instead of this plan's flagged
   uncertainty) — status `"verified"` only for things actually confirmed
   working, not assumed.
4. Update `openspec/project.md`'s gotchas section: replace the current
   single-provider `PAYMENT_PROVIDER` gotcha with the new
   per-gateway-`build_payment_provider(settings, gateway)` shape, and add
   the PayPal-verifies-via-API-call-not-local-HMAC distinction (the one
   architectural outlier among the 5).
5. Update `AGENTS.md`'s "never trust client-supplied money" bullet to
   mention `gateway` is also never client-trusted for anything beyond
   selecting which provider instance to use (price still always re-read
   from the DB regardless of gateway).
6. Delete this file (`PAYMENTS.md`) — everything load-bearing must already
   be captured in the four places above before it goes.
