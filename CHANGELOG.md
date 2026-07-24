# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Owner-scoped reusable palettes.** `UserPalette` now provides validated
  CRUD at `/api/user-palettes/`; the editor can save/apply/delete entries and
  the wizard can deterministically reuse the current user's saved colors while
  keeping `styles.variables` as the only rendering source.
- **Shared AI stream client.** Editor and wizard now consume
  `static/shared/ai-stream.js` for SSE buffering, terminal events, and live
  reasoning display, with a Node regression for chunk-boundary handling.
- **Configurable template palettes.** The editor now exposes a single server
  catalog with Ocean, Forest, Sunset, Neutral, and High Contrast presets,
  custom four-role palettes, accessible contrast feedback, one-step preset
  undo, and responsive 320px/390px controls. `styles.variables` remains the
  rendering source of truth while optional `styles.palette` metadata is
  validated server-side. The wizard accepts a preset context or produces a
  validated AI palette, and published pages, thumbnails, previews, and JSON
  exports preserve the active colors. The durable behavior contract is in
  `openspec/specs/editor/palettes.md`.
- **Opt-in anonymous analytics for published pages.** Public templates now
  offer a consent banner and, only after acceptance, record pseudonymous
  pageviews, session duration, safe click descriptors, sampled pointer activity,
  and page exits. Sellers get an owner-scoped `/analytics/` dashboard with
  period/template filters, session summaries, and a normalized heatmap;
  `purge_analytics` enforces the configured retention window without storing
  IP addresses, auth identity, query strings, or form values.

- **Visible editor exit navigation.** The editor topbar now includes an
  accessible `Salir` link back to the authenticated template gallery, with a
  responsive style and browser regression.
- **Frontend UX/accessibility implementation pass.** Quick-insert presets now
  render allowlisted Tailwind utilities; editor dialogs, tabs, device controls,
  async feedback, mobile layout, wizard asset deletion/cancellation, checkout
  result states, PayU redirect fallback, auth forms, and workspace navigation
  now have explicit keyboard, responsive, loading, success, error, and retry
  behavior. Payment configuration also exposes a non-charging credential
  validation action that checks stored provider readiness without creating a
  checkout session.
- **Free delivery ($0 tracked `Order`) when a seller has no gateway
  enabled.** Rather than 404 or silently give the product away untracked,
  `CheckoutView` now delivers directly and records a real, permanent
  `Order` (`gateway="none"`, `amount_cents=0`, `status=PAID`) — auditable
  exactly like any real purchase.
- **Multi-gateway checkout: Stripe, Mercado Pago, PayPal, Braintree, Wompi,
  PayU, ePayco, Bold.** The buyer picks the gateway at checkout — every
  product card gets one "Pagar con X" button per gateway the seller has
  enabled, never a single global provider. Credentials are configured per
  seller (`/config/`, `PaymentGatewayConfig`, owner-scoped like `/productos/`)
  and encrypted at rest (`apps/storefront/crypto.py`, Fernet keyed from
  `DJANGO_SECRET_KEY`) — never returned by any API response, even to the
  owner who set them. Each gateway has a real implementation plus its own
  `Fake*` variant (`apps/storefront/payments.py`'s `GATEWAY_REGISTRY`); an
  enabled gateway with no/incomplete credentials silently runs its fake
  variant instead of failing, so every button "works" in demo/dev without
  any real keys. `Order` gained a `gateway` field (uniqueness scoped per
  gateway, not global, since two gateways could theoretically collide on
  session-id strings); a shared `GatewayWebhookView` base tries every
  enabled seller's credentials for a gateway until one verifies the inbound
  signature, since a webhook payload carries no explicit seller identity.
  Confidence varies by gateway — Stripe/Mercado Pago/Wompi/PayU/ePayco
  verification was checked against each platform's own docs and is
  regression-tested locally (pure HMAC/checksum, no network); PayPal's
  verification is a real server-to-server API call (mocked in tests);
  Braintree's own SDK verifies its webhooks directly; Bold's real webhook
  spec could never be confirmed (its docs are JS-rendered and returned no
  usable content) so `BoldPaymentProvider.parse_webhook_event` deliberately
  always raises rather than pretend to verify something unconfirmed — see
  `openspec/specs/storefront/spec.md` for the full behavioral contract.
- **AI-designed product cards.** "Insertar producto" used to push a
  hardcoded, completely unstyled node. It now sends an instruction through
  the same AI transform pipeline the chat panel uses: the server feeds the
  model `available_products` (id/name/price/image, populated from the
  requesting user's own active products — never client-supplied) so it
  fills in a properly Tailwind-styled card without ever inventing a product
  id. `editor-ai.js` exposes `EditorAI.requestInstruction` for other editor
  controls to trigger an AI edit the same way.
- **Public template publishing + storefront.** A signed-in user can publish
  a `UserTemplate` (`is_published`/`public_slug`, stable once set) — anyone,
  logged in or not, can then open `GET /t/<slug>/` and see it rendered
  server-side (`apps/editor/rendering.py`'s new `public_page_html`, a full
  standalone document, no editor scripts, same backward-compat posture as
  the Tailwind migration below). New `apps/storefront` app adds `Product`
  (price, optional image, optional downloadable file validated by real
  magic-byte sniffing) and `Order` (the permanent purchase record, created
  only by a signature-verified Stripe webhook, never the checkout-redirect
  view). Checkout (`POST /comprar/<id>/`) always re-reads the price from
  the DB — never trusts the client. A `PaymentProvider` abstraction
  (`FakePaymentProvider`/`StripePaymentProvider`) mirrors the existing
  `AIProvider` swappable pattern — tests and local dev never touch the real
  Stripe API. Digital downloads are served through a token-gated view
  (`GET /descargas/<token>/`, never a static `/media/` URL) with a
  download-count cap; the success page (`GET /gracias/`) explicitly
  handles the webhook-vs-checkout-redirect race condition instead of
  assuming the order already exists. Editor UI: a Publicar/Despublicar
  toggle in the save modal, a `/productos/` management page, and an
  "Insertar producto" control that adds a real product card with a working
  "Comprar" form. Out of scope for this pass (see `BACKLOG.csv` if picked
  up later): Stripe Connect/per-owner payouts, multi-item carts,
  subscriptions, email delivery of the download link, a public
  marketplace/directory. Real Stripe test-mode keys weren't available to
  verify the actual hosted-Stripe-checkout-page round trip in this
  environment — everything else was verified end-to-end with real
  Playwright runs against the fake payment provider.
- **Tailwind CSS migration.** Styling moved from a custom JSON DSL
  (`styles.rules`: AI/editor-authored `{selector, declarations}` objects) to
  Tailwind utility classes on each node's `attributes.class`.
  - `apps/ai_assistant/tailwind_classes.py` — the finite Tailwind class
    allowlist (`is_allowed_tailwind_class`/`check_class_list`), the same
    security role `CSS_PROPERTY_ALLOWLIST` played before. Wired into
    `operations.py` (`set_attribute`/`class`) and `sanitize.py`
    (`check_attributes`, used by full-document validation and
    `add_node`/`replace_node`).
  - Tailwind v4 CLI build pipeline (`pnpm run build:css`): a management
    command (`generate_tailwind_safelist`) materializes the allowlist into a
    sentinel file Tailwind treats as its only content source
    (`tailwind-input.css`'s `@import "tailwindcss" source(none)` +
    `@source`) — necessary because AI-chosen class names never appear in
    any file Tailwind could otherwise scan, and because Tailwind's default
    whole-project auto-scan turned out to compile literally any
    Tailwind-shaped string found anywhere, including test fixtures.
  - The wizard's document generation now authors classes inline during
    structure generation instead of a separate CSS-rules-writing phase; the
    second AI call is repurposed to only set the brand-color palette
    (`styles.variables`).
  - The editor's per-element "Estilo rápido" quick-style panel now toggles
    Tailwind classes instead of writing an inline `style=""` attribute (a
    second, previously-undocumented styling mechanism this migration
    consolidated away).
  - `styles.rules`/`mediaQueries`/`keyframes` remain in the schema and keep
    rendering for backward compatibility with every pre-migration
    `Template`/`UserTemplate`/`Project` row — verified end-to-end (a
    hand-seeded legacy document still renders its old CSS, its gallery
    thumbnail, and remains editable). New content never writes to them;
    `set_css_declaration`/`remove_css_declaration` stay valid operations
    only for editing that legacy content.
- **AI-guided template wizard** (`/wizard/`). Lets a user build a custom
  template from scratch instead of only picking a curated one: a chat asks
  what page they want, the AI generates a tailored question form
  (`POST /api/ai/wizard/questions/`), a review step decides if it's ready or
  needs one clarification via chat (`.../wizard/review/`, up to 5 rounds),
  then the full page document is generated (`.../wizard/generate/`) and
  saved as a `UserTemplate` through the existing `/api/user-templates/`
  endpoint (no new persistence). All three endpoints are SSE, same
  `event: reasoning` → `event: done`/`error` contract as the editor
  assistant. Document generation is itself split into two AI calls —
  structure (HTML tree) then styles (CSS for the classes just introduced) —
  which measurably reduced the model dropping trailing sections on long
  single-shot generations.
- **`document_validation.py`** — validates a FULL AI-generated page document
  (distinct from `operations.py`, which validates incremental edits against
  an existing page). Forces `settings.allowRawHtml`/`allowInlineScripts` to
  `false`, `document.head.links`/`scripts` to `[]`, and rejects any
  unexpected key at every nesting level — the last one specifically catches
  a real failure mode where JSON-repairing a truncated response "fixes" the
  syntax but leaves whole sections as dangling sibling keys instead of
  array items, silently dropping content.
- **Two-role AI model split.** A conversational model
  (`OPENCODE_ZEN_CHAT_MODEL`) handles chat-shaped calls — the wizard's
  question generation and review, and a new instruction-clarification pass
  in the in-editor assistant that rewrites a vague instruction ("hazlo mas
  grande") into an explicit one using page context before the main model
  executes it. The main model (`OPENCODE_ZEN_MODEL`) is reserved for heavy
  structured-JSON generation, where reliability matters more than tone.
- **`AnthropicMessagesProvider`** — some opencode.ai models (MiniMax, the
  Qwen3.7 family) are routed through the Anthropic Messages API
  (`/v1/messages`) rather than OpenAI chat/completions; calling the wrong
  shape doesn't error, it produces intermittent malformed JSON on long
  generations. `build_provider()` now routes by model name
  (`OPENCODE_ZEN_ANTHROPIC_MODELS`).
- **json-repair fallback** for AI responses that fail strict JSON parsing
  (common on long generations — a dropped comma or unterminated string
  near the end). Salvaged output still goes through full validation before
  it's ever exposed, so a "repaired" but semantically broken document is
  still rejected, not saved.
- **Live streamed reasoning** in both AI chat UIs (editor assistant and
  wizard): the model's `<think>` block streams in as it's generated instead
  of only appearing after the full response lands, shown a sentence at a
  time and filtered to skip anything that looks like raw JSON/HTML.
- **`body_outline`** in the edit-transform payload — the real current
  top-level body children (index/tag/class), so the AI can target
  delete/replace paths that actually exist instead of guessing indices from
  a stale mental model (the AI previously had no way to know the page's
  structure in global mode and would say so in its own reasoning).
- **Template picker: base vs user.** `/home/` lists the curated base templates
  (`Template`, global by `slug`, admin-managed, seeded with *Landing (ejemplo)*,
  *En blanco*, *Próximamente*); `/gallery/` lists the signed-in user's own saved
  templates (`UserTemplate`, owner-scoped). A card opens the editor seeded with
  that template (`?t=<slug>` for base, `?ut=<id>` for the user's own). Both are
  Postgres models holding the full editor `state` as JSON.
- **Save as template.** A green "☆ Guardar" button opens a modal offering
  **Crear nuevo** (POST) and, when editing one of your own templates,
  **Actualizar** (PATCH) via `POST/PATCH /api/user-templates/` (owner-scoped).
- **Template version history + rollback.** Updating a `UserTemplate` auto-saves
  the previous `state` as a `UserTemplateRevision`. The save modal's "Historial"
  lists versions with **Restaurar** (applies to the live editor) and **Eliminar**
  per entry (`GET`/`DELETE /api/user-templates/<id>/revisions/…`, owner-scoped).
- **Floating action bar** on the selected preview element — ✎ Editar,
  ⧉ Duplicar, 🗑 Eliminar (buttons reuse the existing core handlers).
- **`@element` reference chip** above the AI composer, showing which element is
  being edited.
- **`OpenCodeZenProvider`** — a third AI provider using OpenCode Zen's
  OpenAI-compatible Chat Completions endpoint
  (`https://opencode.ai/zen/go/v1`). Selectable via `AI_PROVIDER=opencode_zen`
  with `OPENCODE_ZEN_API_KEY` / `OPENCODE_ZEN_MODEL` / `OPENCODE_ZEN_BASE_URL`.
  Lets the server use a flat-price Zen subscription key (server-side, never in
  the browser) instead of metered OpenAI billing.

### Changed

- **pnpm is now the canonical frontend package manager.** The repository pins
  pnpm 10.33.2 in `package.json`, tracks `pnpm-lock.yaml`, and uses frozen
  pnpm installs across local startup, Docker builds, GitHub Actions, and the
  documented test/build commands.
- **Shared UI design tokens across all server-rendered surfaces.** Extracted
  the editor's canonical palette, typography, radius, and shadow variables to
  `static/shared/tokens.css`; editor, wizard, template galleries, storefront,
  checkout result, login, and signup pages now link that stylesheet and use
  the same token names instead of maintaining competing inline sets.
- **Docker build now installs Node 20** (build stage only, never in the
  runtime image) to run the Tailwind CSS build. Debian bookworm's `apt`
  `nodejs` package is 18.x, too old for Tailwind v4 — installed from
  NodeSource instead.
- **`AI_MAX_OPERATIONS` raised again, 50 → 150**, and a new
  **`AI_MAX_OUTPUT_TOKENS`** setting (32000) caps model output tokens
  explicitly — long generations (especially full-document wizard output)
  were getting cut off mid-JSON by the provider's own default cap.
- **CSS property allowlist expanded**: `-webkit-background-clip`,
  `-webkit-text-fill-color`, `-webkit-font-smoothing`, `backdrop-filter`,
  `align-self`, `scroll-behavior`, `overflow-x`/`overflow-y` — all real,
  safe properties the AI was legitimately generating and getting rejected
  for.
- **Provider retries no longer stack.** The OpenAI/Anthropic SDK clients are
  constructed with `max_retries=0`; only our own bounded retry loop retries,
  where before the SDK's own internal retries multiplied on top of it and
  turned a single slow/failing request into several minutes of
  retry-of-retries.
- **Editing UI is now modal-based.** The left panel became an on-demand
  `#elementModal` (inspector + structure, opened by the ✎ button) and a
  `#sectionModal` (Contenido/Diseño/SEO/JSON, opened from the preview toolbar),
  giving the preview the full width.
- **Templates load server-side.** `editor_view` injects the chosen template's
  `state` via `json_script`; an external `seed-loader.js` applies it with
  `EditorCore.commitProposal`. Gallery/home cards are rendered server-side. (The
  loader lives in an external file because the page CSP is `script-src 'self'` —
  inline scripts are blocked.)
- **Global mode is automatic.** The "Modo global" checkbox is hidden; the AI now
  targets the whole page by default and switches to the selected element the
  moment one is picked (clicking empty preview space deselects).
- **Applied-change bubbles are collapsed.** The AI's operation detail list is
  hidden behind a "Ver más" toggle; only the summary paragraph shows by default.
- **`AI_MAX_OPERATIONS` default raised 20 → 50.** A styled section legitimately
  needs one content op plus ~20-30 per-property `set_css_declaration` ops, which
  the old cap rejected as "too many operations".
- **Local development database is PostgreSQL** via the repo `compose.yaml`
  (`DATABASE_URL`); no settings change was needed (`env.db` already supported it).
- **AI API auth is now the Django session + CSRF.** The editor is same-origin
  behind login, so the browser's session cookie authenticates
  `POST /api/ai/editor/transform/` with an `X-CSRFToken` header. The editor view
  sets the CSRF cookie via `ensure_csrf_cookie`.

### Removed

- **The "En blanco" (blank) base `Template`**, via migration
  `0005_remove_blank_template.py`. Superseded by the AI wizard's "create
  from scratch" flow.
- **The "Estructura avanzada" panel** from the editor UI. Its controls remain in
  the DOM (hidden) because the core binds them by id without null-guards.
- **Device Authorization flow and JWT.** Removed the `device_auth` app
  (`/api/auth/device/*`, `/activate/`), `device-auth.js`, the AI panel's connect
  UI, SimpleJWT, and the token/device settings. They only earned their place for
  a decoupled client; the editor is same-origin, so the session is sufficient.
  (Restore from history if a standalone/other-origin editor is ever needed.)

### Fixed

- **Legacy `/comprar/<id>/` (no gateway) 404'd on already-published pages.**
  The multi-gateway checkout migration requires a gateway segment
  (`/comprar/<id>/<gateway>/`), but a buy button baked into a
  `UserTemplate`'s saved state from before that shipped still points at
  the old URL shape — an already-published page's "Comprar" button 404'd.
  A legacy URL now falls back to the seller's first enabled gateway
  instead (still 404s if the seller has enabled nothing at all).
- **Checkout with the fake payment provider got stuck forever on
  "Procesando tu pago…".** With no real Stripe keys configured (the
  project's default dev/test posture), `FakePaymentProvider` marks a
  session paid instantly, but the `Order` was only ever created by
  `StripeWebhookView` — and nothing in dev/test can ever deliver that
  webhook. `CheckoutView` now records the order immediately right after
  creating the session, but only when running against the fake provider;
  real Stripe checkouts are unaffected and still require the actual
  signed webhook.
- **Checkout/webhook rejected logged-in sessions with a CSRF 403.**
  `CheckoutView`/`StripeWebhookView` are `@csrf_exempt` + `AllowAny`, but
  DRF's default `SessionAuthentication` runs its own CSRF check independent
  of that decorator whenever it authenticates a request via session —
  a logged-in visitor (e.g. the product's own owner testing their "Comprar"
  button) got `CSRF Failed: CSRF token missing.` despite the view being
  explicitly exempt. Fixed with `authentication_classes = []` on both (no
  reason to authenticate a fully public endpoint at all).
- **AI rejected `max-w-4xl` and other named max-width classes.** The
  `tailwind_classes.py` `max-w` utility family only allowed the numeric
  spacing scale, missing Tailwind's separate named container-width scale
  (`max-w-4xl`, `max-w-prose`, `max-w-none`, etc.) — one of the most common
  classes for a page container, rejected outright as "disallowed Tailwind
  class". `w`/`min-w`/`h`/`min-h`/`max-h` are unaffected.
- **AI transform rejected legacy classes on selected editor nodes.** Existing
  pages created before the Tailwind migration contain semantic classes such as
  `site-header`, which are valid for backward-compatible rendering but not
  valid AI output classes. The transform now removes only those legacy tokens
  from the selected-node context before generation; generated operations still
  use the strict Tailwind allowlist. The offline fake provider also emits an
  allowlisted highlight class.
- **AI couldn't embed YouTube/Vimeo videos.** `<iframe>` was fully forbidden
  by `sanitize.py`, so any instruction to embed a video failed with a generic
  "cambios no válidos" error. `<iframe>` is now allowed, restricted to a
  `src` allowlist (`youtube.com/embed/`, `youtube-nocookie.com/embed/`,
  `player.vimeo.com/video/`) so arbitrary iframe embeds (a clickjacking/
  phishing risk on now-publicly-published pages) are still rejected. The AI
  prompt now converts `watch` URLs to `embed` URLs and uses `aspect-video`
  instead of an arbitrary `pb-[56.25%]` padding hack. The allowlist alone
  wasn't enough to make embeds visible: the CSP's `frame-src 'self'` and
  `editor-core.js`'s own separate client-side tag list both independently
  blocked the same embed and needed the matching same-origin allowlist.
- **AI color instructions had no effect on gradient backgrounds.** For an
  element with an opaque `background: linear-gradient(...)`, the model emitted
  `background-color`, which renders *under* the gradient and stays invisible.
  The prompt now instructs the model to use the `background` shorthand for
  element fills.
- **CSS allowlist rejected per-side borders.** `border-top`/`-right`/`-bottom`/
  `-left` were missing from `sanitize.py` (while their `margin-*`/`padding-*`
  counterparts were present), so AI edits using a per-side border (e.g. a
  navbar's `border-bottom`) failed as "CSS property not allowed".
- **Floating action bar vanished in global mode.** The bar was hidden whenever
  the (now removed) global-mode checkbox was checked, regardless of selection;
  it now shows purely on element selection.
- **Version history no longer padded on no-op saves.** `perform_update` snapshots
  a revision only when the `state` actually changes, so restoring the current
  version (or a name-only PATCH) no longer creates redundant history entries.
- **CSS mojibake in the AI chat UI.** `editor.css` had no declared charset, so
  the browser guessed one that mangled the non-ASCII arrows/bullets used by
  the collapsible details toggles. Fixed with a literal `@charset "UTF-8";`
  as the file's first bytes.
- **Undo after picking a template loaded the wrong page.** The editor always
  booted with a built-in default page as `historyPast[0]`; loading a chosen
  template pushed onto that stack instead of replacing it, so the very
  first undo after opening a template jumped back to the default page
  instead of doing nothing. `EditorCore.loadSeed()` now resets history
  instead of pushing onto it.
- **AI edits in global mode targeted the wrong or nonexistent elements.**
  Without `body_outline`, the AI had no way to know the page's real
  structure and would guess indices for delete/replace — it said as much in
  its own reasoning ("no tengo visibilidad del árbol... voy a asumir").

## [0.1.0] - 2026-07-20

### Added

- **Django project scaffold** managed with `uv` (Python 3.12), split settings
  (`base` / `development` / `production`), WSGI/ASGI, and a `/healthz/` endpoint.
- **accounts app** — login/logout via Django auth views; `next=` support so
  activation can bounce through login.
- **device_auth app** — self-hosted OAuth 2.0 Device Authorization Grant:
  - `POST /api/auth/device/code/`, `POST /api/auth/device/token/`,
    `GET|POST /activate/`, `POST /api/auth/token/refresh/`.
  - Device code stored only as a SHA-256 hash; readable `user_code` without
    ambiguous characters; single-use codes; states
    `pending/approved/denied/consumed/expired`.
  - `authorization_pending` / `slow_down` / `expired_token` / `access_denied`
    responses; per-IP + per-scope throttling; SimpleJWT access/refresh issuance.
  - Refresh token delivered as an `HttpOnly`, `SameSite=Lax` cookie; access
    token kept in memory only.
- **ai_assistant app** — `POST /api/ai/editor/transform/`:
  - Input sanitizer (`sanitize.py`) and operation validator (`operations.py`)
    enforcing tag/attribute/CSS/URL allowlists, integer paths, cycle checks,
    and size/op limits — independent of the model.
  - Swappable provider interface with `FakeAIProvider` (offline/tests) and
    `OpenAIProvider` (Responses API, JSON Schema, timeout, bounded retries).
  - Structured operation protocol: `set_text`, `set_attribute`,
    `remove_attribute`, `set_style_variable`, `set_css_declaration`,
    `remove_css_declaration`, `add_node`, `replace_node`, `duplicate_node`,
    `delete_node`, `move_node`, `add_section`.
- **projects app** — `Project` + `ProjectRevision` API, owner-scoped (no IDOR),
  revisions tagged `manual` / `ai` / `import`.
- **editor app** — serves the visual editor at `/editor/`.
- **Frontend split** of the monolithic `editor.html` into a Django template,
  `editor.css`, `editor-core.js` (verbatim editor + `window.EditorCore`
  facade), `device-auth.js`, and `editor-ai.js` — all existing behavior
  preserved (selection, history, drag & drop, import/export, flicker-free
  preview, responsive views).
- **AI panel** ("Asistente IA" tab): connection status, device connect,
  selected-element info, global mode, instruction field, generate/preview/
  apply/discard, loading and readable errors.
- **`applyAIOperations`** — deterministic, `eval`-free operation applier;
  applying a proposal produces a single undo step.
- **Security** — CSRF for Django views, JWT for the API, closed CORS, secure
  headers + CSP middleware, secure cookies / HSTS / SSL redirect in production,
  request size cap, throttling, secret-free logs.
- **Tests** — pytest suite (device auth, AI transform, operation validation,
  project IDOR) plus a framework-free Node test for `applyAIOperations`.
- **Docker** — multi-stage image (`uv sync --frozen --no-dev`, non-root,
  collectstatic, Gunicorn, healthcheck) and a `compose.yaml` with PostgreSQL.

[Unreleased]: https://example.com/compare/v0.1.0...HEAD
[0.1.0]: https://example.com/releases/tag/v0.1.0
