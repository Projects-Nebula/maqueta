# FEATURE.md — Publish templates publicly (storefront + blog reading)

**Audience**: an agent executing this feature end to end, autonomously,
without stopping for clarification. Every decision that would normally be
"ask the user" has already been made below — follow it as written. If you
hit a fact about the codebase that contradicts something stated here, trust
the code and adapt, but do not silently change the target architecture
(Section 1) without flagging it loudly in your final report.

**This document must not survive the feature.** Every fact worth keeping
(what shipped, why, how it was verified, what's still open) belongs in the
project's permanent docs — `BACKLOG.csv`, `CHANGELOG.md`, `learnings.jsonl`,
`AGENTS.md`, `openspec/project.md` — not here. Section 11 ("Close-out") is
the last phase, not an afterthought: do it before deleting this file, and
only delete this file once those other docs already say everything in it
that matters. `REFACTOR.md` (Tailwind CSS migration) went through the exact
same lifecycle this session — read `git log --oneline` for
`docs: remove REFACTOR.md...` and the commit before it
(`docs: record Tailwind migration outcome...`) as a concrete template for
how to close this one out.

---

## 0. Goal

Two currently-impossible things, both riding the same mechanism:

1. A signed-in user can **publish** a `UserTemplate` they built in the
   editor — it gets a public URL. Anyone, logged in or not, can open that
   URL and see the rendered page.
2. If that page has **products** on it (placed by the owner via a new
   editor control), an anonymous visitor can **buy one** — a real checkout,
   real money, via Stripe. If the page is just content (a "blog" — text,
   images, no products), publishing it is already the whole feature: an
   anonymous visitor reading it needs nothing further.

Today: zero public surface exists. Every page-serving view requires login
(`@login_required` on all four of `apps/editor/views.py`'s HTML views,
confirmed this session). This feature adds the first ever anonymous-facing
routes in the project — treat every new view here as hostile-input-facing
by default, same posture the AI endpoints already have
(`apps/ai_assistant/sanitize.py`'s whole reason to exist).

---

## 1. Non-negotiable architecture decisions

### 1.1 Publishing is a flag + slug on `UserTemplate`, not a new model

Add two fields to `apps/editor/models.py`'s `UserTemplate`:
`is_published` (`BooleanField`, default `False`) and `public_slug`
(`SlugField`, `unique=True`, `null=True`, `blank=True` — null until first
published). A migration is required. Do **not** introduce a separate
"PublishedTemplate" model — it's the same content, one source of truth,
matching how `Template`/`UserTemplate` already work (one row, one `state`).

`public_slug` is generated server-side on first publish
(`slugify(name) + "-" + secrets.token_hex(3)` — the random suffix avoids
collisions across users with the same template name; it does **not** need
to be unguessable/secret, since the page is meant to be public once
published — unpublishing just flips `is_published` back to `False`, the
slug is kept so re-publishing returns the same URL). Never regenerate the
slug on every publish/unpublish cycle — it's meant to be a stable, shareable
link once it exists.

### 1.2 The public page is rendered by a NEW, separate server-side renderer — not the thumbnail one, not editor-core.js

`apps/editor/rendering.py`'s `thumbnail_srcdoc` is explicitly a "much
smaller, read-only subset" (its own docstring) — no SEO `<head>` metadata,
no `htmlAttributes`, no real `<title>`. The public page needs the FULL
document: doctype, `htmlAttributes` (`lang`/`dir`), every `<meta>`, a real
`<title>`, the Tailwind link, legacy `styles.rules`/`variables`/
`mediaQueries` CSS (same backward-compatibility posture the Tailwind
migration established — a template published before or after that
migration must render identically). This is a Python port of
`editor-core.js`'s `buildHtmlDocument()` (`static/editor/editor-core.js:
1078-1103`), reusing `rendering.py`'s existing `_render_node`/
`_render_attributes`/`_render_styles`/`_render_rule_list` — add a new
`public_page_html(state, *, title_fallback: str) -> str` function
alongside `thumbnail_srcdoc` in the same module (they're siblings: one
render, two callers, two output shapes).

The public page **never** loads `editor-core.js`, `editor-ai.js`,
`autosave.js`, `save-template.js`, or any other editor script — it is a
static, read-only HTML document. No `data-vjpb-path` attributes, no
selection/inspector machinery, nothing editable. Product "Buy" controls
(1.5) are the only interactive element, and they're a plain `<form>` POST,
no JS framework needed.

### 1.3 Products are a real Django model, not a `state.products` JSON blob

Money needs relational integrity (no float-precision bugs, real foreign
keys for orders, queryable history) — this is exactly why `UploadedAsset`
is a real model instead of a base64 blob in `state.assets`, and the same
reasoning applies harder here. New model in `apps/editor/models.py`:

```python
class Product(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price_cents = models.PositiveIntegerField()  # never a float — Stripe wants integer minor units too
    image = models.ForeignKey(UploadedAsset, null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Currency is a single, fixed, project-wide setting (`DEFAULT_CURRENCY` in
`config/settings/base.py`, e.g. `"usd"`) — no per-product or per-template
currency choice in this pass (Section 9 explicitly defers multi-currency).

Owner-scoped CRUD via a new `ProductViewSet` (`apps/editor/views.py`,
mirrors `UserTemplateViewSet`'s `get_queryset` owner-scoping exactly — same
IDOR posture: `Product.objects.filter(owner=self.request.user)`), mounted
in `apps/editor/api_urls.py` next to the existing router registration.

### 1.4 Products are referenced in the page tree the same way uploaded images already are

`apps/ai_assistant/wizard_service.py` already has a proven pattern for
"the AI/editor picks from a list of the owner's own already-validated
resources, never authors the registry itself" (`available_images` →
server-built `state.assets`, shipped this session, commit `ac75c39`).
Products reuse the identical shape: a product card is a plain node with a
`data-product-id="<int>"` attribute on its wrapping element, e.g.:

```json
{"type": "element", "tag": "div", "attributes": {"class": ["...", ...], "data-product-id": "42"},
 "children": [ <name, price, image, buy button as ordinary child nodes> ]}
```

`data-product-id` is validated the same way any other attribute is
(`apps/ai_assistant/sanitize.py`'s `check_attributes` / `operations.py`'s
`_validate_one`) — add it to a small allowlist of "reference" attributes
(not a URL, not a class list; just an integer-string check) rather than
inventing a new node type or a `components` system. **Do not** repurpose
the existing forced-empty `components` key for this — that key stays
frozen exactly as `document_validation.py` already documents ("no
components feature yet"); products are a parallel, separate mechanism, not
an implementation of that placeholder.

At **render time** (both editor preview and the public page), a
`data-product-id` on a node is resolved server-side/client-side against the
owner's real `Product` rows to render current name/price/image — but the
simplest correct choice for this pass: the product's name/price/image are
written as literal text/attributes directly into the child nodes by the
editor UI when the product card is inserted (same as how an uploaded
image's `<img src>` is a literal URL, not resolved indirectly at render
time) using the values Product had at insert time. `data-product-id` is
carried along purely so the "Buy" button knows which product to check out
— it is not a live-binding/templating mechanism. If a product's price
changes after being placed on a page, the on-page display until the owner
re-edits, but the actual checkout ALWAYS charges the *current* `Product.
price_cents` from the DB (1.6) — never trust the price rendered in old
page HTML.

### 1.5 The "Buy" control is a plain HTML form, no client JS required

```html
<form method="post" action="/comprar/42/">
  {% csrf_token is NOT applicable — anonymous POST, see 1.6 %}
  <button type="submit">Comprar</button>
</form>
```

This keeps the public page dependency-free (no JS framework, no fetch
calls, works with JS disabled) and matches "no editor scripts on the public
page" (1.2).

### 1.6 Checkout: Stripe Checkout Sessions (redirect), single platform merchant account, no Stripe Connect

Real payment processing from scratch is out of scope by construction —
use Stripe's hosted Checkout page (redirect flow): the buyer's card details
never touch this server, minimizing PCI scope to "SAQ A" (the lightest
tier). New view `POST /comprar/<product_id>/` (`apps/editor/views.py` or a
new `apps/storefront/` app — see 1.9 for the app-boundary decision):

1. Look up `Product.objects.get(pk=product_id, is_active=True)` — 404 if
   missing/inactive. Never trust a price, currency, or product name from
   the request body; only the ID.
2. Create a Stripe Checkout Session (`stripe.checkout.Session.create`,
   `mode="payment"`, one line item built entirely from the DB row:
   `price_data={"currency": settings.DEFAULT_CURRENCY, "product_data":
   {"name": product.name}, "unit_amount": product.price_cents}`,
   `quantity=1`, `success_url`/`cancel_url` pointing back at the template's
   public page with query params for a thank-you/cancelled banner).
3. Redirect (302) to `session.url`.

**Single merchant of record**: every payment goes to the *platform's own*
Stripe account (one `STRIPE_SECRET_KEY` for the whole project), not to the
individual template owner's own Stripe account. Real per-owner payouts
(Stripe Connect: onboarding, KYC, split payments) is a materially larger
feature (compliance, identity verification flows, a payouts UI) — explicit
non-goal for this pass (Section 9). Money still gets *tracked* per owner
(the `Order` model, 1.7, records which product/owner it was for) so payouts
are a reachable follow-up, just not built now.

**CSRF**: the checkout POST is exempt from CSRF (`@csrf_exempt` on this one
view only) — an anonymous visitor has no session/CSRF cookie to present,
and the transaction's integrity comes from server-side product lookup, not
from a form token. This is the *only* CSRF-exempt view in the project;
do not broaden the exemption pattern anywhere else.

### 1.7 `Order` model records completed payments, created only from a verified Stripe webhook

```python
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"

    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="orders")
    stripe_session_id = models.CharField(max_length=255, unique=True)
    buyer_email = models.EmailField(blank=True)
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=8)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
```

New view `POST /webhooks/stripe/` (`@csrf_exempt`, the second and only
other CSRF-exempt view): verifies the request signature with
`stripe.Webhook.construct_event(payload, sig_header,
settings.STRIPE_WEBHOOK_SECRET)` — **reject anything that fails
verification** (400, log it, do not process). On a verified
`checkout.session.completed` event, `get_or_create` an `Order` keyed by
`stripe_session_id` (idempotent — Stripe retries webhook delivery, this
must never double-record). The webhook is the *only* place `Order` rows get
created — never create one directly from the checkout-redirect view, since
that view runs before payment is confirmed.

### 1.8 New settings: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `DEFAULT_CURRENCY`

Add to `config/settings/base.py`'s `env.Env(...)` schema (same pattern as
every other secret already there — `OPENAI_API_KEY`, `OPENCODE_ZEN_API_KEY`
— string default `""`, never required at import time so the app still
boots without them in dev/tests). Add to `.env.example` with empty values
and a comment. The Stripe *publishable* key is not needed for this pass —
pure redirect-to-Checkout requires only the secret key server-side.

New dependency: `stripe` (add to `pyproject.toml`, `uv add stripe`).
`FakeAIProvider`-style test double needed too (see Section 6) — do not let
tests hit the real Stripe API.

### 1.9 App boundary: new `apps/storefront/` app, not bolted onto `apps/editor/`

`Product`/`Order`/checkout/webhook views are a distinct bounded concern
(payments) from `apps/editor` (page authoring/rendering) — new Django app
`apps/storefront/` (models, views, urls, serializers, migrations, tests),
registered in `INSTALLED_APPS`. The **public template page view** itself
(`GET /t/<slug>/`) stays in `apps/editor/views.py` + `apps/editor/urls.py`
next to `UserTemplate` — it's still fundamentally "render a template",
just without login. Only the money-handling surface (`Product`, `Order`,
checkout, webhook) moves to the new app. `Product.image` FKs
`apps/editor.UploadedAsset` across the app boundary — that's fine and
already how `apps/projects` FKs `settings.AUTH_USER_MODEL` across apps.

### 1.10 Rate limiting on every new anonymous-facing endpoint

Reuse `rest_framework.throttling.ScopedRateThrottle` exactly as already
used everywhere else in the project (`apps/ai_assistant/views.py`,
`apps/editor/views.py`'s `WizardImageUploadView`) — it already keys by IP
for unauthenticated requests (confirmed this session:
`ScopedRateThrottle.get_cache_key` falls back to `self.get_ident(request)`
when `request.user` isn't authenticated), so no new throttle mechanism is
needed, just new scopes in `config/settings/base.py`'s
`DEFAULT_THROTTLE_RATES`: `"public_template_view": "60/m"`,
`"checkout_session_create": "10/m"`. The Stripe webhook endpoint is
**not** rate-limited by IP (Stripe's own IPs, signature-verified) — do not
throttle it, a dropped legitimate webhook silently loses an order.

---

## 2. Target data model — before / after

**`UserTemplate`** (new fields only):
```
is_published: bool = False
public_slug: str | None = None  # unique, set on first publish
```

**New `Product`** (owned by a user, not tied 1:1 to a specific
`UserTemplate` — the same product could in principle be placed on more than
one of the owner's pages):
```
owner, name, description, price_cents, image (-> UploadedAsset), is_active,
created_at, updated_at
```

**New `Order`**:
```
product (-> Product, nullable on delete), stripe_session_id (unique),
buyer_email, amount_cents, currency, status, created_at
```

**Product card node** (inside `state.document.body`, same shape as any
other node — nothing new at the JSON-schema level, just a new attribute):
```json
{"type": "element", "tag": "div",
 "attributes": {"class": [...Tailwind classes...], "data-product-id": "42"},
 "children": [
   {"type": "element", "tag": "h3", "attributes": {}, "children": [{"type": "text", "value": "Nombre del producto"}]},
   {"type": "element", "tag": "p", "attributes": {}, "children": [{"type": "text", "value": "$19.99"}]},
   {"type": "element", "tag": "img", "attributes": {"src": "/media/...", "alt": "..."}, "children": []},
   {"type": "element", "tag": "form", "attributes": {"data-buy-form": "42"}, "children": [
     {"type": "element", "tag": "button", "attributes": {}, "children": [{"type": "text", "value": "Comprar"}]}
   ]}
 ]}
```
(`data-buy-form`'s value is the same product id — the editor/renderer needs
to turn this into a real `<form method="post" action="/comprar/42/">` at
render time; decide during implementation whether that's done by
`sanitize.py`'s node validation + `rendering.py`'s node renderer both
special-casing `data-buy-form`, or by the editor inserting the literal
`action` URL directly into `attributes` when placing the block — the
latter is simpler and consistent with 1.4's "literal values at insert
time" choice; prefer it unless a concrete reason emerges not to.)

---

## 3. Phases — execute in order, commit after each, gates green every time

Same discipline as `REFACTOR.md` used: `uv run pytest`,
`uv run ruff check .`, `uv run ruff format --check .`, `npm test`, and for
anything UI-facing, a **real Playwright run against a live server** — not
optional, this feature's entire value proposition is "an anonymous person
can actually see/buy something," which unit tests alone cannot prove.

### Phase 1 — `is_published`/`public_slug` + public read-only page

1. Migration adding `is_published`/`public_slug` to `UserTemplate`.
2. `apps/editor/rendering.py`: new `public_page_html(state, *,
   title_fallback)` (1.2).
3. New view `public_template_view(request, slug)` in `apps/editor/
   views.py` — no `@login_required`. 404 if `UserTemplate.objects.filter
   (public_slug=slug, is_published=True)` is empty (same 404 for
   "doesn't exist" and "unpublished", 1.1). Renders `public_page_html`
   directly as an `HttpResponse` (not a Django template — the content
   *is* the whole HTML document already).
4. URL: `path("t/<slug:slug>/", public_template_view, name="public-template")`
   in `apps/editor/urls.py`.
5. `UserTemplateSerializer`: add `is_published`, `public_slug` (both
   read-only from the API's perspective for now — publishing happens via a
   dedicated action, not a raw PATCH, see step 6) so the editor UI can
   read current publish state.
6. New `@action(detail=True, methods=["post"])` on `UserTemplateViewSet`:
   `publish` (sets `is_published=True`, generates `public_slug` if absent)
   and `unpublish` (`is_published=False`, slug untouched, 1.1). Owner-scoped
   via the existing `get_queryset`.
7. Editor UI: in the existing "Guardar" modal (`static/editor/
   save-template.js`, `templates/editor/editor.html`), add a "Publicar"/
   "Despublicar" toggle button (only shown once the template has an id,
   i.e. after first save — mirrors how "Actualizar"/history already only
   show for an owned `UserTemplate`) and, once published, show the public
   URL with a copy-to-clipboard control.
8. Tests: model migration, serializer fields, `publish`/`unpublish`
   actions (owner-scoped — another user's template 404s), the public view
   (published → 200 with expected content; unpublished/nonexistent → 404;
   confirm no `data-vjpb-path` / editor script tags appear in the output).
9. **Manual verification (required)**: publish a template via the UI in a
   real browser, open the public URL in a fresh/incognito context (no
   session), confirm it renders. Confirm a legacy `styles.rules`-based
   template (same one used for `REFACTOR.md`'s Phase 8 check, or a
   freshly seeded equivalent) also renders correctly on its public page.

### Phase 2 — `apps/storefront/` app: `Product` model + owner-scoped CRUD

1. `apps/storefront/` app (`models.py`, `serializers.py`, `views.py`,
   `urls.py`, `api_urls.py`, `admin.py`, migrations). Register in
   `INSTALLED_APPS`.
2. `Product` model (1.3). `ProductViewSet` (owner-scoped, mirrors
   `UserTemplateViewSet`). Mount at `/api/products/`
   (`config/urls.py`).
3. A minimal products management UI — reuse the existing wizard-image-
   upload endpoint (`/api/user-templates/wizard-images/`) for the
   product's `image` field (same `UploadedAsset` model, no new upload
   code needed) plus a simple form (name, description, price) — a new
   small page/panel is acceptable here (does not need to be inside the
   main editor SPA-like flow); simplest: a `/productos/` page
   (`@login_required`) listing/creating/editing the owner's products.
4. Tests: owner-scoping (IDOR), price is always a positive int, image FK
   nullable/optional.
5. **Manual verification**: create a product with an image through the
   UI, confirm it's owner-scoped (a second test user can't see/edit it).

### Phase 3 — Insert a product card into a page + the "Buy" form

1. Editor UI: a new "Insertar producto" control (in the existing
   add-section/insert-content flow, `static/editor/editor-core.js`) that
   lists the current owner's active products (fetched from
   `/api/products/`) and, on pick, inserts the node structure from
   Section 2 via the existing `add_node`/`add_section` mechanism — same
   path a manual "add section" already takes, just with a pre-built
   product-card node instead of a blank one.
2. `apps/ai_assistant/sanitize.py`: allow `data-product-id`/`data-buy-form`
   as a recognized (non-URL, non-class) attribute — validate it's a
   string of digits, nothing else (mirrors how other non-URL attributes
   are minimally checked today).
3. `apps/editor/rendering.py`'s node renderer (`_render_node`) and
   `editor-core.js`'s equivalent: when a node carries `data-buy-form`,
   its literal `attributes.action` (set at insert time per the Section 2
   node-model decision) is what actually gets rendered — no special-casing
   needed at render time if the editor writes the real `action` URL
   directly when inserting the block. Confirm this is suffient before
   adding any render-time special case.
4. Tests: inserting a product card round-trips through
   `applyAIOperations`/`add_node` validation without errors; a
   `data-product-id` with a non-digit value is rejected.
5. **Manual verification**: insert a product card in the editor, confirm
   it appears in the live preview with a real "Comprar" button.

### Phase 4 — Stripe checkout + webhook

1. `uv add stripe`. Settings (1.8): `STRIPE_SECRET_KEY`,
   `STRIPE_WEBHOOK_SECRET`, `DEFAULT_CURRENCY` (default `"usd"`).
   `.env.example` entries (empty values).
2. `Order` model (1.7) + migration.
3. `POST /comprar/<int:product_id>/` view (1.6) — `@csrf_exempt`,
   `ScopedRateThrottle` scope `checkout_session_create`. 404 on missing/
   inactive product. Redirects to the Stripe-hosted session URL.
4. `POST /webhooks/stripe/` view (1.7) — `@csrf_exempt`, signature
   verification, idempotent `Order` creation on
   `checkout.session.completed`.
5. A thin Stripe client wrapper (e.g. `apps/storefront/payments.py`)
   with a swappable interface — mirrors this project's existing
   `AIProvider`/`FakeAIProvider` pattern (`apps/ai_assistant/providers.
   py`) exactly: a `PaymentProvider` protocol with `create_checkout_
   session(...)` and a `FakePaymentProvider` for tests that returns a
   canned session object without calling the real Stripe API. Select via
   a setting (`PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="fake"
   if not STRIPE_SECRET_KEY else "stripe")` — same "fake by default, real
   only with a key" posture `AI_PROVIDER` already has).
6. Tests (all against `FakePaymentProvider`, never the real Stripe API —
   same reasoning `FakeAIProvider` exists for): checkout view redirects
   with a valid product; 404s on inactive/missing product; webhook
   creates exactly one `Order` even if delivered twice (idempotency);
   webhook rejects a bad signature; price/currency in the created
   session always come from the DB row, never from request data (write
   a test that POSTs a forged price and confirms it's ignored).
7. **Manual verification (needs real Stripe test-mode keys — flag this
   requirement explicitly to the user if the environment doesn't have
   them, same as this project already flags "needs a real
   `OPENAI_API_KEY`" for `OpenAIProvider`)**: with `STRIPE_SECRET_KEY`/
   `STRIPE_WEBHOOK_SECRET` set to Stripe test-mode values, run the full
   flow for real in a browser — public page → Comprar → land on Stripe's
   actual hosted checkout page (test-mode banner visible) → complete with
   a Stripe test card (`4242 4242 4242 4242`) → confirm redirect to the
   success URL → confirm the webhook fired (use `stripe listen --
   forward-to` locally, or check the Stripe dashboard's test-mode event
   log) → confirm an `Order` row exists with `status="paid"`. If test-mode
   keys are genuinely unavailable in this environment, say so explicitly
   in the final report rather than claiming this was verified — this
   mirrors the project's existing rule (`AGENTS.md`) that passing tests
   verifies the code, not the feature.

### Phase 5 — Docker/CI/docs parity

1. `Dockerfile`/`compose.yaml`: no new build step needed (pure Python
   dependency, no client asset to compile) — confirm `uv sync` picks up
   `stripe` and the image still builds (`docker build`, same verification
   discipline as every other Docker-touching change this session).
2. `.github/workflows/ci.yml`: no changes needed unless new env vars are
   required for tests to import cleanly (they shouldn't be, since
   `PAYMENT_PROVIDER` defaults to `fake` and settings never require the
   Stripe keys to be non-empty).
3. `AGENTS.md`/`openspec/project.md`: add the storefront app to the
   project-layout listings, note the fake/real payment-provider switch
   next to the existing `AI_PROVIDER` note, document the new anonymous
   routes and the two CSRF-exempt views as a explicit gotcha (same
   treatment `editor-core.js`'s "don't touch this" gotcha already gets).

---

## 4. Explicitly out of scope

Do not build these now — flag them as new `BACKLOG.csv` rows if they come
up, do not silently expand scope mid-implementation:

- **Stripe Connect / per-owner payouts.** All payments land in one
  platform Stripe account (1.6); distributing money to template owners is
  a distinct, much larger feature (KYC/onboarding/compliance).
- **Multi-item cart / quantity selection.** One product, one "Buy now"
  button, quantity fixed at 1.
- **Multi-currency.** One project-wide `DEFAULT_CURRENCY`.
- **Subscriptions / recurring billing.** `mode="payment"` only, never
  `mode="subscription"`.
- **Inventory/stock tracking.** `is_active` is a manual on/off switch, not
  a stock count.
- **Refunds UI.** Handle refunds manually via the Stripe dashboard for now;
  no in-app refund flow.
- **A public marketplace/directory of published templates.** Publishing
  gives a direct link, not a searchable public listing of everyone's pages.
- **Multi-post blogs.** A published template is one page. Individual blog
  posts with their own sub-URLs (`/t/<slug>/posts/<post-slug>/`) is a
  separate, larger feature if it's ever wanted.
- **AI-authored product placement** (the wizard/editor-transform prompts
  proactively suggesting/placing products, the way they already know about
  `available_images`). Nothing here blocks adding that later — the
  `data-product-id` mechanism (1.4) is deliberately the same shape as the
  asset-reference one specifically so that extension is cheap — but wiring
  the AI prompts to know about products is not required for this feature
  to deliver its value (a human placing a product card manually is enough)
  and should not be added speculatively.
- **Sales analytics/dashboard.** `Order` rows exist and are queryable; no
  UI is built to summarize them.

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| Public view leaks unpublished/private content | 404 for both "doesn't exist" and "not published" (never distinguish); every query filters `is_published=True` explicitly, never relies on a slug being "secret." |
| Checkout charges the wrong amount | Price/currency are read from the `Product` row inside the checkout view at request time — never accepted from the client. Test this explicitly (Phase 4 step 6). |
| Webhook double-processes a payment | `stripe_session_id` is `unique=True`; use `get_or_create` keyed on it, never a plain `create`. |
| Forged webhook calls create fake "paid" orders | Signature verification (`stripe.Webhook.construct_event`) is mandatory before touching the DB; a failed verification is a 400, not a soft-fail. |
| `stripe` Python package differs from what's drafted here by version | Pin a version in `pyproject.toml` after `uv add stripe` resolves one, and verify the exact `checkout.Session.create`/`Webhook.construct_event` call shapes against the installed version's own docs before trusting this document's exact kwarg names. |
| Public page accidentally loads editor JS (XSS/editing surface exposed to anonymous users) | `public_page_html` (1.2) is a from-scratch renderer that only ever includes Tailwind's compiled CSS + rendered content — it must never reference `editor-core.js`/`editor-ai.js`/etc. Add a test asserting none of those script filenames appear in its output. |

---

## 6. Testing plan (summary — see each phase for specifics)

New test files expected: `tests/test_public_template_view.py`,
`tests/test_products.py` (or under a `apps/storefront/tests/` if that
app-local convention is preferred — check whether `apps/ai_assistant`/
`apps/editor` keep tests under the shared root `tests/` dir, which this
session's work always did, and match it), `tests/test_checkout.py`,
`tests/test_stripe_webhook.py`. All Stripe-touching tests use
`FakePaymentProvider` (Phase 4 step 5) — never call the real Stripe API in
`pytest`. Extend `tests/js/apply.test.js` only if a new operation-shape
needs client-side coverage (unlikely — Section 1.5 deliberately avoids new
operation types).

## 7. Manual verification checklist (do not skip, do not assume)

- [ ] Publish a template; open its public URL in a logged-out browser
      context; content renders.
- [ ] Unpublish it; the same URL now 404s.
- [ ] A legacy (`styles.rules`-based, pre-Tailwind-migration-shaped)
      template still renders correctly on its public page.
- [ ] The public page's HTML contains no reference to any editor `.js`
      file.
- [ ] Create a product with an image; it's owner-scoped (a second test
      user cannot see/edit it via the API).
- [ ] Insert a product card in the editor; it appears in the live preview
      with a working "Comprar" button.
- [ ] End-to-end checkout against Stripe test mode (Phase 4 step 7) — or
      an explicit, honest note in the final report if test-mode keys
      weren't available in this environment.
- [ ] A forged/tampered checkout POST (wrong price implied by a modified
      request) still charges the real DB price.
- [ ] A replayed webhook event does not create a second `Order`.

---

## 8. Close-out — the ONLY way this file is allowed to go away

Do this as the final phase, in order, before deleting `FEATURE.md`:

1. **`BACKLOG.csv`**: add one row per phase actually shipped (or one
   summary row for the whole feature, matching how the Tailwind migration
   got one row — `BACKLOG.csv`'s existing "Tailwind CSS migration" row is
   the template to follow: `status=done`, real `files` list, real
   `verification` values, the actual commit hash). If Phase 4's Stripe
   test-mode verification genuinely couldn't be run, the row must say so
   honestly (e.g. `verification=pytest;playwright_partial` and a note in
   `description` — do not claim `manual_live_model_verification`-equivalent
   coverage that didn't happen).
2. **`CHANGELOG.md`**: a new `### Added` entry under `[Unreleased]`
   describing what shipped, in the same voice/detail level as the
   "Tailwind CSS migration" entry already there.
3. **`learnings.jsonl`**: append one JSON line per verified, reproducible,
   generalizable finding actually hit while building this (e.g. anything
   about Stripe's Python SDK, webhook testing, `ScopedRateThrottle`'s
   anonymous-request behavior if anything surprising came up). Skip this
   step content-wise (not structurally) if nothing genuinely reproducible
   surfaced — do not invent filler entries just to have one.
4. **`AGENTS.md`** / **`openspec/project.md`**: update the project-layout
   listings and gotchas sections per Phase 5 step 3.
5. **Only then**: `rm FEATURE.md`, commit it in the same spirit as
   `docs: remove REFACTOR.md — migration executed, no longer needed as a
   live plan`.

If you reach the end of Phase 4 and something in Sections 1-7 turned out to
be wrong or impossible as written, that correction belongs in step 2-4
above (the permanent docs), not left undocumented — the whole point of
this close-out phase is that deleting this file loses nothing.
