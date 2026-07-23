# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Tailwind CSS migration.** Styling moved from a custom JSON DSL
  (`styles.rules`: AI/editor-authored `{selector, declarations}` objects) to
  Tailwind utility classes on each node's `attributes.class`.
  - `apps/ai_assistant/tailwind_classes.py` — the finite Tailwind class
    allowlist (`is_allowed_tailwind_class`/`check_class_list`), the same
    security role `CSS_PROPERTY_ALLOWLIST` played before. Wired into
    `operations.py` (`set_attribute`/`class`) and `sanitize.py`
    (`check_attributes`, used by full-document validation and
    `add_node`/`replace_node`).
  - Tailwind v4 CLI build pipeline (`npm run build:css`): a management
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
