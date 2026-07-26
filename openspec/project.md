# Project — Visual AI Editor

> Session bootstrap. Read this first when picking the project up in a new
> session. It captures what the project is, how it is laid out, how to run it,
> and the conventions that are NOT obvious from the code.

## What it is

Django backend + AI assistant wrapped around an existing visual HTML/JSON page
editor. Users pick a starting **template** (a curated base one from `/home/`, or
one of their own saved ones from `/gallery/`) — or build one from scratch via
the **AI wizard** at `/wizard/` — select an element in a live preview, describe
a change in natural language, and the backend returns **validated structured
operations** they preview and apply as a single undo step. The editor is
served behind login and same-origin, so the browser's **session cookie (with
CSRF)** authenticates API calls — no API key ever reaches the browser, and no
token/device flow is needed.

## Stack

- Python 3.12, managed exclusively with `uv` (never pip/poetry/pipenv).
- Django 5.2, Django REST Framework.
- django-environ, django-cors-headers, whitenoise, gunicorn.
- AI providers: `OpenAIProvider` (OpenAI SDK, Responses API),
  `OpenCodeZenProvider` (OpenAI SDK, OpenAI-compatible chat/completions),
  `AnthropicMessagesProvider` (`anthropic` SDK, for OpenCode Zen models
  routed via `/v1/messages` — see gotchas), and `FakeAIProvider` (offline,
  what tests use). `build_provider()` picks per-call by model name.
  `json-repair` salvages malformed AI JSON before falling back to an error.
  `jsonschema` for the operation schema.
- **PostgreSQL for local dev and production** (via `DATABASE_URL`; the repo
  `compose.yaml` provides a `db` service). SQLite is supported only as an
  explicit isolated-test or fallback override.
- pytest + pytest-django + pytest-mock, ruff (lint + format).
- Node 20+ with pnpm 10.33.2 for frontend dependencies and Tailwind/Node
  tests; the version is pinned in `package.json` and `pnpm-lock.yaml` is the
  only frontend dependency lockfile. Enable it with `corepack enable pnpm`.
- Docker + Docker Compose.

## Layout

```
config/            settings base/development/production, urls, CSP middleware, wsgi/asgi
apps/accounts      login/logout
apps/editor        serves /editor/ /home/ /gallery/ /wizard/; Template ·
                   UserTemplate · UserTemplateRevision · UserPalette ·
                   UploadedAsset (gained placeholder_color) · AuditEvent
                   (owner-scoped, self-pruning via AuditEvent.record(),
                   see gotchas) models, admin, owner-scoped UserTemplate
                   and UserPalette DRF APIs (template revisions
                   history/restore/delete), GET /api/audit-events/;
                   palette catalog/validation; ensure_csrf_cookie
apps/ai_assistant  sanitize · operations · providers (Anthropic/OpenAI-compatible/
                   fake, model-based routing) · schema · prompts · service
                   (EditorAIService: chat model clarifies instruction → main
                   model generates operations) · serializers · views (edit-time
                   transform; also POST /api/ai/editor/import-html/, non-AI) ·
                   html_import (deterministic HTML→node converter, same
                   sanitize_node gate as AI operations) · wizard_service
                   (WizardAIService: same two-role split; generate is itself
                   2 calls — structure then palette) · wizard_views ·
                   document_validation (sanitizes a FULL generated document,
                   strict key checks at every level) · sse
apps/projects      Project + ProjectRevision API (owner-scoped)
apps/storefront    Product · Order (gateway-scoped) · PaymentGatewayConfig
                   (owner-scoped, encrypted credentials) models; ProductViewSet
                   + PaymentGatewayConfigViewSet (both owner-scoped);
                   /comprar/<id>/<gateway>/ (+ legacy /comprar/<id>/),
                   /webhooks/<gateway>/ (8 of them), /gracias/, /config/,
                   /descargas/<token>/ (all anonymous-facing except /config/);
                   payments.py (PaymentProvider ABC, one real + one Fake*
                   per gateway behind GATEWAY_REGISTRY — Stripe/Mercado
                   Pago/PayPal/Braintree/Wompi/PayU/ePayco/Bold — same
                   swappable pattern as apps.ai_assistant.providers);
                   crypto.py (Fernet encryption for stored credentials)
apps/analytics     Pseudonymous opt-in visitor/session/event models, public
                   consent/collect endpoints, owner-scoped dashboard APIs,
                   heatmap aggregation, admin, and purge_analytics command
templates/         registration/login · editor/editor.html · editor/home.html ·
                   editor/gallery.html · editor/template_wizard.html ·
                   storefront/products.html · storefront/payment_config.html ·
                   storefront/success.html · storefront/checkout_cancel.html ·
                   storefront/payu_redirect.html
                   analytics/dashboard.html
static/editor/     editor.css · editor-core.js · editor-ai.js (also owns the
                   shared EditorModals dialog manager, see gotchas) ·
                   seed-loader.js · save-template.js · html-import.js ·
                   command-palette.js · wizard.css · template-wizard.js ·
                   autosave.js · tailwind-input.css (source) ·
                   tailwind.css (compiled, gitignored, `pnpm run build:css`)
static/shared/     tokens.css (shared cross-page design tokens) ·
                   ai-stream.js (shared AI SSE/reasoning client)
static/storefront/ products.js (/productos/) · payment-config.js (/config/)
static/analytics/  public-tracker.js/css · dashboard.js/css
tests/             pytest + tests/js/ (Node) + tests/e2e/ (Playwright)
openspec/          this spec set (project.md · specs/ · changes/)
```

## Templates

- `Template` (base catalog, global, `slug`) shown on `/home/`; `UserTemplate`
  (per-user, owner FK) shown on `/gallery/`. Both hold the full editor `state`
  as JSON (`Template.state` may be null → built-in default page).
- `editor_view` reads `?t=<slug>` (base) or `?ut=<id>` (user, owner-scoped)
  and injects the state server-side via `{{ ...|json_script:"template-seed" }}`;
  `seed-loader.js` applies it with `EditorCore.commitProposal`. Both gallery
  pages render cards server-side (no client fetch).
- "☆ Guardar" saves the current state as a `UserTemplate` via the owner-scoped
  `UserTemplateViewSet` (POST create / PATCH update, no IDOR). Base templates are
  seeded by data migration `apps/editor/migrations/0002_seed_templates.py`.
- Updating a `UserTemplate` auto-snapshots the previous state into a
  `UserTemplateRevision` (only on real change); the save modal's "Historial"
  lists them with restore/delete via `…/user-templates/<id>/revisions/`.
- There is no "blank" base `Template` anymore (removed by data migration
  `apps/editor/migrations/0005_remove_blank_template.py`) — its role is now
  the **wizard** (`/wizard/`, `apps/editor/views.py::template_wizard_view`):
  a chat asks what page the user wants, the AI generates a tailored question
  form (`POST /api/ai/wizard/questions/`), a review step decides if it's
  ready or needs one clarification via chat (`POST /api/ai/wizard/review/`,
  looped up to 5 rounds — `MAX_REVIEW_ROUNDS` in `template-wizard.js`), then
  `POST /api/ai/wizard/generate/` produces the document in **two** AI calls
  (`WizardAIService.stream_generate_document`): structure (HTML tree, no
  styles) first, then the four palette variables (the Tailwind classes are
  authored in the structure call). If the user selected a preset or an
  owner-scoped saved palette, the server applies its catalog values exactly
  and skips the style-color call; otherwise
  the second call is normalized to `styles.palette.source: "ai"` — a single
  call asking for both
  was where the model most reliably ran out of steam and silently dropped
  the trailing keys. `components`/`assets` (always `{}`, no image-upload
  feature exists yet) are force-injected in Python rather than trusted from
  the model — it reliably omitted them too, even in the shorter call.
  The assembled document is validated whole by
  `document_validation.sanitize_document` (distinct from
  `operations.validate_operations`, which only validates incremental edits
  against an existing page). None of the three wizard endpoints persist
  anything — the client saves the result via the same
  `POST /api/user-templates/` the editor's "☆ Guardar" already uses.
  All three are SSE (same `event: reasoning` → `event: done`/`error` contract
  as `/api/ai/editor/transform/`, see `apps/ai_assistant/sse.py`).
- The in-editor assistant (`EditorAIService.stream_generate_operations`) has
  the same two-role split: a chat model rewrites the user's raw instruction
  ("hazlo mas grande") into an explicit one using page context
  (`_clarify_instruction`, falls back to the raw instruction on any
  provider error — it's an enhancement, not a hard requirement) before the
  main model generates operations from it.

## Commands

```bash
./setup.sh                               # interactive prerequisites/dependencies/PostgreSQL bootstrap
./run-local.sh                            # canonical Django development start
./mockup.sh                               # destructive local reset + deterministic demo data
uv sync
docker compose up -d --wait db              # local PostgreSQL (creds editor/editor/editor)
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver          # http://localhost:8000/home/
# Quality gates (all must pass before "done"):
uv run ruff check .
uv run ruff format --check .
AI_PROVIDER=fake uv run pytest            # deterministic AI-backed test gate
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
pnpm test
pnpm run build:css                          # required after Tailwind/frontend changes
uv run python manage.py purge_analytics --days=90
# Or use the canonical local bootstrap (starts PostgreSQL automatically):
./run-local.sh
# Docker:
docker compose up --build
```

`run-local.sh` uses port 8000 by default and detects an occupied port before
installing/building anything. Use `PORT=8001 ./run-local.sh` when another
development server already owns 8000.
`run-local.sh`/`setup.sh` both run `CI=true pnpm install --frozen-lockfile`
— without `CI=true` this hangs/aborts
(`ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`) whenever the script runs with
no TTY (an agent, a cron job) and pnpm wants to confirm recreating
`node_modules`. Real GitHub Actions runners already set `CI=true`
themselves, so this was invisible in CI — only found by actually running
`run-local.sh` live outside an interactive terminal. **Verified** 2026-07-26
via a real end-to-end run (server responded, migrations applied) after the
fix; `BACKLOG.csv` row 84.
`setup.sh` is the interactive prerequisite bootstrap: it asks before installing
missing uv/Python, Node/pnpm, or Docker requirements, stops when a required
installation is refused, prepares dependencies/Tailwind/PostgreSQL, and
applies migrations without starting Django.
The end-to-end workflow was verified on 2026-07-24 with
`UV_CACHE_DIR=/tmp/uv-cache ./setup.sh`: PostgreSQL reported healthy, Tailwind
generated 30,184 classes, and migrations reported no pending changes. Starting
Django remains the responsibility of `run-local.sh`.
`mockup.sh` is the local demo-data bootstrap: it migrates, flushes the database
and referenced media files, then creates deterministic records across auth,
editor, projects, storefront, and analytics. It refuses non-development
settings unless `MOCKUP_ALLOW_NON_DEBUG=1` is explicitly set. The commented
`MOCKUP_USERNAME`, `MOCKUP_EMAIL`, and `MOCKUP_PASSWORD` entries in
`.env.example` optionally override the printed demo credentials; keep
`MOCKUP_ALLOW_NON_DEBUG` disabled outside an explicitly controlled local run.
`stop-local.sh` stops the Django development server without touching the
database by default; `./stop-local.sh --db` also stops PostgreSQL while
preserving its volume.

Frontend changes additionally require a real-browser run of the relevant
`tests/e2e/` specs. When Chromium system libraries are unavailable on the host,
use the version-matched official Playwright container described in `AGENTS.md`.

## Conventions

- **Delegation & context optimization:** see `CLAUDE.md` (auto-loaded). Push
  delegable work to sub-agents on lighter models (haiku/sonnet); keep only
  architecture, security-critical logic, and tricky integration inline on Opus.
- **Dependencies + Python via `uv` only.** No pip/poetry/pipenv.
- **Code, comments, UI copy, identifiers default to English.** User-facing app
  strings (login, activate, editor panel) are Spanish to match the editor.
- **Security is server-side and model-independent.** `sanitize.py` +
  `operations.py` are the single source of truth for what a node tree / AI
  operation may contain. Never trust paths, nodes, or operations from the
  browser or the model.
- **AI never returns free HTML** — only the validated operation protocol.
- **Never expose `OPENAI_API_KEY` to the frontend.** Never send the full JSON
  document to the AI; send only the selected node + nearby context + design
  variables + instruction.
- **One AI apply = one undo step** (`EditorCore.commitProposal`).
- Migrations excluded from ruff.
- **Analytics is intentionally opt-in.** `/t/<slug>/` does not create an
  analytics cookie or event before consent. The visitor UUID is separate from
  Django authentication/session identity; collect accepts only bounded,
  normalized event descriptors. Run `purge_analytics` on a schedule because
  retention is an operational command, not request-time deletion.

## Non-obvious gotchas

- **CSP blocks inline scripts.** `config/middleware.py` sets
  `script-src 'self'` (no `'unsafe-inline'`), so any inline `<script>…</script>`
  with executable JS is SILENTLY blocked by the browser — no console error
  unless you look. ALL page logic MUST live in an external `static/editor/*.js`
  file (`script-src 'self'`). Inline `type="application/json"` data (e.g.
  `json_script`) and inline styles (`style-src 'unsafe-inline'`) are fine; same
  origin fetch is fine (`connect-src 'self'`).
- `static/editor/editor-core.js` is the original `editor.html` IIFE verbatim
  with a `window.EditorCore` facade injected **inside** the IIFE (top-level
  `let state`/`selectedPath` are not on `window`). Do not "clean it up" — it is
  intentionally near-byte-identical. To integrate with the core (e.g.
  `commitProposal`, `clearSelection`), ADD a method to the facade object at the
  end; the surrounding editor-ai.js drives it. Never patch the IIFE body.
- Dev overrides static storage to plain `StaticFilesStorage` so pages render
  without `collectstatic`; production uses the manifest storage. After deleting
  a `.py` module, `rm` its stale `__pycache__/*.pyc` or the dev reloader
  keeps importing it → crash loop.
- Production exempts `/healthz/` from SSL redirect for the container healthcheck.
- The AI panel is event-driven, not polled: `editor-core.js` dispatches
  `vjpb:selection-change` (from `highlightSelectedPreviewElement`) and
  `vjpb:state-committed` (from `commitHistorySnapshot`) on the preview
  document; `editor-ai.js`/`autosave.js` listen for those instead of a
  timer, rebinding on iframe `load` since `srcdoc` reload replaces
  `contentDocument`.
- **Styling is Tailwind CSS**, not custom CSS rules. The AI/editor style
  elements via `set_attribute`/`class` with Tailwind utility classes,
  validated against the finite allowlist in
  `apps/ai_assistant/tailwind_classes.py` (`is_allowed_tailwind_class`/
  `check_class_list`) — the same security role `CSS_PROPERTY_ALLOWLIST`
  played before. `styles.rules`/`mediaQueries`/`keyframes` still exist and
  still render (`buildCss()`, `rendering.py`) for backward compatibility
  with pre-Tailwind saved pages, but new content never writes to them;
  `set_css_declaration`/`remove_css_declaration` stay valid operations only
  for editing that legacy content. `styles.variables` (CSS custom properties,
  e.g. `--color-primary`) remains the only rendered color source — Tailwind
  classes reference it via `bg-[var(--color-primary)]`. Optional
  `styles.palette` metadata contains only `id`, `name`, and `source`; the
  canonical catalog and validation live in `apps/editor/palettes.py`, with the
  complete contract in `openspec/specs/editor/palettes.md`. Legacy states
  without metadata are accepted without rewrite and are not inferred as a
  preset from matching values. A selected wizard preset is applied server-side
  exactly; an unselected result is marked `source: "ai"`.
- **Legacy classes are context-only compatibility data.** Pre-Tailwind saved
  nodes can still contain semantic classes such as `site-header` and
  `container`. `TransformRequestSerializer` runs `sanitize_context_node`,
  which removes those non-Tailwind tokens recursively before the AI sees a
  selected node while retaining the same structural, URL, attribute, depth,
  and size checks. `sanitize_node` and operation validation remain strict, so
  this compatibility path cannot authorize legacy classes in AI output.
- **Reusable palettes are owner-scoped catalog data.** `UserPalette` entries
  are served through `/api/user-palettes/`, injected into the editor/wizard,
  and resolved through the authenticated owner before wizard generation.
  Applying one copies only its four role values into `styles.variables`; the
  document stores safe provenance metadata and never depends on the catalog at
  render time.
- **AI stream transport lives in `static/shared/ai-stream.js`.** The editor
  assistant and wizard provide only surface-specific status/scroll callbacks;
  SSE buffering, terminal event collection, and live reasoning filtering stay
  in the shared module. Load it before either consumer.
- **Cross-page UI tokens live in `static/shared/tokens.css`.** The editor,
  wizard, galleries, storefront management/result pages, and auth templates
  link this stylesheet and use its canonical `--app-bg`, `--panel-bg`,
  `--border`, `--text`, `--muted`, `--primary`, `--font-sans`, `--radius`, and
  `--shadow` variables. Do not add another page-level `:root` palette; keep
  layout and component-specific rules local until a concrete reuse case
  justifies extraction.
- **`UXUI.md` is the current frontend audit source of truth.** The 2026-07-24
  browser pass found the shared token layer healthy and the resulting
  behavior/accessibility implementation pass complete. Read that file before
  adding another modal or management-page flow; it records the historical
  findings, the completed acceptance matrix, the non-charging gateway
  credential validation contract, the template palette UX, and the required
  browser checks.
- Tailwind's CLI auto-scans the whole project for candidate class names by
  default — **verified** this compiles literally any Tailwind-shaped string
  found anywhere, including test fixtures (a security-test string
  `"bg-[url(evil)]"` got compiled into the output before this was caught).
  `tailwind-input.css` uses `@import "tailwindcss" source(none)` plus an
  explicit `@source` pointing only at the generated safelist file
  (`.tailwind-safelist.txt`, from `generate_tailwind_safelist`) — never
  remove `source(none)`.
- `AI_MAX_OPERATIONS` (default 150) caps ops per AI response.
- `AI_PROVIDER` selects the provider; `fake` (default when no key) makes the
  whole flow work offline and is what tests rely on. Use
  `AI_PROVIDER=fake uv run pytest` for the deterministic local quality gate;
  live-provider runs are separate model verification and can produce
  non-allowlisted Tailwind classes.
- **Multi-gateway checkout, per-seller, not a global `PAYMENT_PROVIDER`
  setting anymore.** The buyer picks the gateway at checkout
  (`POST /comprar/<id>/<gateway>/`); credentials live in `PaymentGatewayConfig`
  (owner-scoped like `Product`, one row per seller per gateway, encrypted
  at rest via `apps/storefront/crypto.py` — Fernet keyed from
  `DJANGO_SECRET_KEY`, so rotating that key without a migration plan makes
  every stored credential unreadable) managed at `/config/`. An enabled
  gateway with no/incomplete credentials silently runs its own `Fake*`
  provider (`apps/storefront/payments.py`'s `GATEWAY_REGISTRY`) instead of
  failing — tests must never hit a real gateway API; use the matching
  `Fake*` class. `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/
  `PAYMENT_PROVIDER` settings no longer exist.
- `apps/storefront`'s checkout and all 8 gateway webhook views
  (`/webhooks/<gateway>/`) are the only `@csrf_exempt` views in the project
  — an anonymous buyer and the gateway itself have no CSRF cookie to
  present. Do not broaden that exemption elsewhere; each webhook's
  integrity instead comes from that gateway's own signature verification
  (`GatewayWebhookView` tries every enabled seller's credentials for that
  gateway until one verifies — a webhook payload carries no explicit
  seller identity), and checkout never trusts a client-supplied price
  (always re-reads `Product.price_cents` from the DB).
- `Order` (`apps/storefront`) gained a `gateway` field — uniqueness is
  scoped to `(gateway, gateway_session_id)`, not a single global session id
  (two gateways could theoretically collide on session-id strings). It's
  created by the verified webhook for a real gateway — the checkout-
  redirect view runs before payment is confirmed, so `GET /gracias/` (the
  success page) must not assume the `Order` already exists; it falls back
  to a direct `PaymentProvider.retrieve_session` lookup instead of
  fabricating a download link. **Two narrow exceptions, both verified live
  bugs before their fixes**: (1) with a `Fake*` provider there is no real
  gateway server to ever deliver a webhook, so `CheckoutView` calls the
  shared `_record_order_for_session()` directly right after creating the
  session (buyer was stuck on "Procesando tu pago…" forever otherwise);
  (2) when the seller has **zero** gateways enabled at all, `CheckoutView`
  delivers the product directly and records a real `Order`
  (`gateway="none"`, `amount_cents=0`, `status=PAID`) rather than 404ing or
  giving it away untracked. Never take either shortcut for a real
  configured gateway — real payments still require the actual signed
  webhook.
- **`/comprar/<id>/` (no gateway segment) still exists as a legacy URL** —
  a buy-form `action` baked into a `UserTemplate`'s saved state from before
  multi-gateway checkout shipped points there, and it's a LITERAL value in
  stored JSON that a URLconf change never retroactively updates.
  **Verified** a real already-published page 404'd after the gateway-
  segment URL shipped; it now falls back to the seller's first enabled
  gateway (alphabetical) or the zero-gateway free-delivery path above. Any
  future URL-shape change for a route whose exact string gets saved into
  content (not just navigated to) needs the same kind of explicit
  backward-compat path, not just an updated `URLconf`.
- `CheckoutView`/every gateway webhook view also set
  `authentication_classes = []` (not just `permission_classes = [AllowAny]`)
  — DRF's default `SessionAuthentication` runs its OWN CSRF check
  independent of `@csrf_exempt` whenever it successfully authenticates a
  request via session cookie. **Verified**: a logged-in visitor (e.g. the
  product's own owner testing their "Comprar" button) got a 403
  `CSRF Failed` despite the view being explicitly exempt, until
  `authentication_classes = []` removed the reason to authenticate the
  requester at all. The `api`/`anon_api` test fixtures use
  `force_authenticate`, which bypasses this whole pipeline — regression-
  testing this class of bug needs a real `client.login()` session with
  `enforce_csrf_checks=True`.
- **`stripe.Webhook.construct_event` returns a `StripeObject`, not a plain
  dict** — no `.get()`, doesn't match `isinstance(x, dict)`.
  `StripePaymentProvider.parse_webhook_event` normalizes via
  `event.to_dict()` before returning. This was a real, previously-latent
  bug: an `isinstance(dict)` branch silently always took the wrong path for
  every real (non-fake) Stripe webhook, since only `FakePaymentProvider`
  had ever been exercised through that code path before this was caught.
- `GET /t/<slug>/` (public template page) and `GET /descargas/<token>/`
  (digital download) both 404 identically for "doesn't exist" and
  "not allowed" — never let either be distinguishable, so neither an
  unpublished template nor an unpaid order can be enumerated.
- `AI_MAX_OUTPUT_TOKENS` (default 32000) caps model output tokens. Without it
  set explicitly (or set too low), a full-page wizard generation (lots of
  styles.rules JSON) can get cut off mid-response by the provider's own
  default cap, producing invalid/truncated JSON (`AIResponseFormatError`) —
  this is NOT a prompt or validation bug, it's starving the model of output
  budget.
- MiniMax (via `opencode_zen`) rejects JSON Schema **type unions**
  (`"type": ["string", "null"]`) in `response_format.json_schema` with a
  400 *before generation even starts* — use a single type (e.g. plain
  `"string"`) and handle the null/empty case in Python instead
  (`wizard_service.py`'s `stream_review_answers` already does this for
  `clarification`). Not obvious from the error, which just says "mismatched
  type with value" at a byte offset into the schema.
- **Some OpenCode Zen models need `/v1/messages`, not `/v1/chat/completions`.**
  Per OpenCode Zen's own model table: Grok/GLM/Kimi/DeepSeek/MiMo are
  OpenAI-compatible; MiniMax and the Qwen3.7 family are Anthropic-Messages-
  compatible. Calling the wrong shape does NOT error cleanly — it produces
  intermittent malformed JSON on long generations, which looks exactly like
  "the model is unreliable" until you check which endpoint it actually
  wants. `providers.OPENCODE_ZEN_ANTHROPIC_MODELS` is the routing table;
  `build_provider()` picks `AnthropicMessagesProvider` vs
  `OpenCodeZenProvider` by model name. Before adding a new model to
  `OPENCODE_ZEN_MODEL`/`OPENCODE_ZEN_CHAT_MODEL`, check which endpoint it
  needs and update that set if it's Anthropic-Messages-compatible.
- **`deepseek-v4-pro`/`deepseek-v4-flash` are broken on this account**,
  failing identically via both protocols with `"Error from provider
  (Console Go): Upstream request failed"` (400) — confirmed not a protocol
  issue (tested both), it's opencode.ai's own upstream for that model
  family. Don't re-diagnose this from scratch; check with opencode.ai
  support first.
- **`json-repair` can "fix" JSON syntax while corrupting document structure.**
  A dropped comma/bracket near a truncation point can get "repaired" into
  syntactically valid JSON that closes an array early and leaves what
  should have been array items as dangling sibling keys one level up
  instead (a whole section silently missing from `body.children`,
  reappearing as stray `type`/`tag`/`attributes`/`children` keys on
  `document` itself). `document_validation.py` guards against this with
  exact key-set checks (`set(x.keys()) == {...}`) at every nesting level,
  not just presence checks — this is why those checks exist and shouldn't
  be loosened without understanding this failure mode first.
- **`.env` changes need a full server restart, not just a save.** Django's
  `StatReloader` (`runserver`'s autoreload) only watches `.py`/`.html`/`.js`
  — `.env` is read once at process start via `environ.Env.read_env()` in
  `config/settings/base.py`. Changing a model name or API key in `.env` and
  expecting the next request to pick it up silently doesn't work; kill and
  restart `runserver`.
- Rejection reasons for wizard document generation are logged at `INFO`
  (not `DEBUG`) permanently in `wizard_service.py`
  (`"rejected AI-generated document: <reason>"`) — the model's output isn't
  deterministic, so a failure doesn't reliably reproduce on retry; the
  reason needs to already be in `server.log` the first time, not require
  flipping the log level and asking for another attempt.
- **`max-w-*` has its own named container-width scale** (`xs`..`7xl`, `full`,
  `min`, `max`, `fit`, `prose`, `none`), separate from the numeric spacing
  scale shared by `w`/`h`/`min-w`/`min-h`/`max-h`
  (`tailwind_classes.py`'s `MAX_WIDTH_NAMED_SCALE`). **Verified** a real AI
  generation attempt was rejected for `max-w-4xl` — one of the most common
  Tailwind classes for a page container — before this was added; a
  screenshot showing a vague "cambios no válidos" error can have a
  completely different real cause than it looks like, always check
  `server.log`'s exact rejection string first.
- **`<iframe>` embeds (YouTube/Vimeo) need THREE separate places updated
  together**, or the change silently half-works with no clear error:
  1. `apps/ai_assistant/sanitize.py`'s `IFRAME_SRC_ALLOWED_PREFIXES` (server
     validation — arbitrary iframe src stays forbidden, a real
     clickjacking/phishing risk on now-publicly-published pages).
  2. `static/editor/editor-core.js`'s `renderNode()` — a SEPARATE,
     hand-maintained tag/src check for the live preview (this file is
     intentionally not refactored, see below).
  3. The CSP `frame-src` directive in BOTH
     `config/settings/development.py` and `production.py`.
  Also: `templates/editor/editor.html`'s `#previewFrame` needs
  `allow-scripts` in its `sandbox` attribute (not just `allow-same-origin`)
  for a nested video iframe to run its own player JS — sandbox flags
  cascade to nested browsing contexts. **Verified** all three/four gaps
  independently, one at a time, via live Playwright reproduction — fixing
  only one still leaves the embed broken with a different symptom each
  time (rejected server-side → CSP-blocked → "Unable to execute
  JavaScript").
- **`Error 153` on an embedded YouTube video is a `localhost`/`127.0.0.1`
  origin issue, not a maqueta bug.** Verified via YouTube's own public
  oEmbed endpoint (`curl
  "https://www.youtube.com/oembed?url=...&format=json"` → 200 with a valid
  embed snippet) that the video itself is embeddable; the rejection is
  YouTube's own origin check. Re-test on a real deployed domain before
  assuming a regression.
- **"Insertar producto" and the double-click product-link/image-picker are
  deliberately different mechanisms**, not an inconsistency: inserting a
  new product card routes through the AI (`EditorAI.requestInstruction`,
  server-populated `EditorContext.available_products`, never
  client-supplied) since it needs to generate a styled layout: linking an
  existing button or swapping an image is a deterministic client-side edit
  (`getNode`/`getParentInfo`/`updateAll` in `editor-core.js`, no AI
  round-trip) since it's wiring, not content generation. Both were
  explicit, asked-for product decisions — see `BACKLOG.csv` rows 44/45.
- **Quick-insert presets use the Tailwind allowlist.** Hero, Beneficios,
  Texto, Imagen, Llamado, and Footer now emit finite, compiled utility classes;
  the old semantic-class regression is closed in `BACKLOG.csv` rows 43 and
  55. Keep new preset classes in the allowlist and add a browser regression for
  any new preset.
- **`EditorModals` (in `editor-ai.js`) discovers modals by querying
  `.panel-modal[role="dialog"]` once at load — a template-defined modal
  needs no manual registration, but a modal built dynamically in JS after
  that query already ran (e.g. `command-palette.js`'s overlay) must call
  `EditorModals.register(el)` once after building it.** A hand-maintained
  5-id array previously backed this and `#htmlImportModal` was never added
  to it — clicking "Pegar HTML" silently did nothing, undetected by any
  test (`BACKLOG.csv` row 81). All 6 shared dialogs
  (`elementModal`/`sectionModal`/`paymentLinkModal`/`imagePickerModal`/
  `saveTemplateModal`/`htmlImportModal`) plus the command palette now have
  e2e coverage that they open — see `tests/e2e/editor_ux.spec.js` and
  `tests/e2e/command_palette.spec.js`.
- **`AuditEvent.record()`** (not `AuditEvent.objects.create()`) is the only
  way to write an audit row — it creates the event then prunes that
  owner's events to `AuditEvent.RETENTION_LIMIT` (100), so the table never
  grows unbounded and never needs a separate purge command. Action set:
  `ai_transform`, `ai_wizard_generate`, `template_create`, `template_save`
  — no `palette_apply` (purely client-side, no server round-trip to hook
  into) and no separate `revision_restore` (restoring already goes through
  the same PATCH `template_save` covers).
- **HTML paste import (`apps/ai_assistant/html_import.py`) drops the raw
  `class` attribute always, but maps a small allowlisted set of `style`
  declarations to their exact Tailwind class** (`STYLE_TO_TAILWIND`:
  `text-align`/`font-weight`/`font-style`/`text-decoration`), each
  re-validated through `is_allowed_tailwind_class`. This is deliberately
  NOT a general CSS-to-Tailwind converter — only exact `(property, value)`
  matches; resist growing it into one. Everything else in `style` is
  dropped and counted in the response's `skipped_attributes`.

## Related durable context

- `CHANGELOG.md` — what shipped, by version.
- `BACKLOG.csv` — the delivery log: every shipped item (status is always
  `done` in practice — this isn't a forward-looking task tracker),
  structured for filtering (status/area/category/verification/blocked_by).
- `learnings.jsonl` — proven technical findings, one per real discovery;
  never store secrets.
- `openspec/specs/` — current capability specs (source of truth for behavior).
- `openspec/specs/editor/palettes.md` — active palette contract, catalog, AI
  constraints, legacy behavior, and verification evidence.
- `openspec/specs/analytics/spec.md` — consent, bounded collection,
  owner-scoped reporting, heatmap, and retention contract.
- `TODO.md` — concise status index only; completed implementation checklists
  belong in the capability spec and delivery records.
- `openspec/changes/` — in-flight change proposals (delta specs).
- `PROPOSAL.md` — analysis of ideas borrowed from an external project
  (`corebunch/instatic`), each tied to a maqueta area, with a final
  done/deferred status per item. `PLAN.md`/`REVIEW.md` are the historical
  execution-order and self-review record for that effort (`BACKLOG.csv`
  rows 71–83) — read them for the "why," not as active planning documents;
  the loop they document converged with nothing further pending.
- Session memory: `~/.claude/projects/-home-sebitcode-projects-maqueta/memory/`.
