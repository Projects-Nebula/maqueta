# Backlog

Pending work, ordered roughly by priority. Items map to known limitations and
natural next steps. Checked = done.

## High priority

- [ ] **Wizard `generate` step is still intermittently unreliable.** Even
  with the Anthropic-Messages protocol fix, the two-phase split
  (structure/styles), json-repair, and forcing always-empty
  `components`/`assets` in code, the model (mimo-v2.5-pro) occasionally
  still fails validation on a full-document generation — variance in the
  model's own output, not a code bug. Rejection reason is now logged
  permanently at INFO in `wizard_service.py` (`"rejected AI-generated
  document: <reason>"`) with the exact offending keys, so the next failure
  is diagnosable from `server.log` directly. Next lever to try: reduce the
  requested scope further (fewer sections, simpler CSS) to shorten
  generations and lower truncation/omission risk.
- [ ] **`deepseek-v4-pro`/`deepseek-v4-flash` unavailable via opencode_zen.**
  Both fail identically through both the OpenAI-compatible and Anthropic
  Messages protocols with `"Error from provider (Console Go): Upstream
  request failed"` (400) — confirmed not a protocol issue on our side.
  Follow up with opencode.ai support before retrying.
## Medium priority

- [x] **Event-driven selection in the AI panel.** 400ms poll replaced: core
  dispatches `vjpb:selection-change` on the preview document from
  `highlightSelectedPreviewElement` (`editor-core.js`); `editor-ai.js` listens
  for it, rebinding on iframe `load` since `srcdoc` reload replaces
  `contentDocument`.
- [x] **Non-modal AI preview.** Investigated: this described dead code, not
  the shipped UX. The real flow auto-applies AI changes immediately
  (`commitProposal`, one undo step) with a post-hoc "Descartar" button — there
  is no live preview stage where a manual edit could be lost. The
  `previewProposal`/`cancelProposal`/`__aiPreviewBackup` skeleton this item
  referred to was never wired up; removed as dead code
  (`static/editor/editor-core.js`). If a true propose-then-confirm UX is
  wanted later, that's a new feature, not this bugfix.
- [x] **Autosave projects.** `?p=<uuid>` now loads a `Project` in the editor
  (`apps/editor/views.py`, latest `ProjectRevision` if one exists, else the
  project's own `state`). `editor-core.js` dispatches `vjpb:state-committed`
  whenever a history snapshot lands (reuses the existing debounce/flush
  points, no new hook into its internals); `static/editor/autosave.js`
  listens, debounces 3s, and `POST`s `/api/projects/{id}/revisions/`. Added
  the same revision-retention cap (20) to `apps/projects/views.py` that
  `UserTemplate` already has. Verified end-to-end with a real Playwright run
  (edit → wait past debounce → revision persisted via the API).
- [x] **Registration flow.** `SignupView` (`apps/accounts/views.py`) uses
  Django's stdlib `UserCreationForm` — no custom fields, no new dependency —
  logs the new user in immediately and redirects to the editor, same as
  login. `/signup/` linked from `login.html`. Verified with a real
  Playwright signup run end to end.
- [x] **Frontend test runner.** `npm test` runs `node --test tests/js/**/*.test.js`
  (`package.json`); wired into `.github/workflows/ci.yml`.
- [x] **Template thumbnails.** Server-side mini-render (`apps/editor/rendering.py`)
  walks `state.document.body` + `state.styles` into a standalone HTML doc, shown
  scaled 0.25x in a `pointer-events: none` `<iframe srcdoc>` on each gallery card
  (`templates/editor/home.html`, `gallery.html`). No new deps, no headless
  browser at request time. Falls back to the first-letter avatar when `state`
  is null/empty (e.g. `Template.state = None` uses the built-in default page).
  Verified with a real Playwright screenshot against a seeded template.
- [x] **Image upload for the wizard.** `POST /api/user-templates/wizard-images/`
  (`WizardImageUploadView`) — Pillow re-encodes every upload from scratch
  (`apps/editor/image_processing.py`: format/size validated, downscaled to
  1600px long edge, always re-saved as JPEG, stripping EXIF), owner-scoped
  `UploadedAsset` model, per-user upload cap. Registered in `state.assets`,
  but never AI-authored: `wizard_service.py` builds `assets` server-side from
  exactly what the client already uploaded, and the model only picks a URL
  from that list to put in `<img src>` — closes what would otherwise have
  been the same "AI can smuggle anything into an unvalidated JSON blob" gap
  the `@media` fix closed above. `document_validation.py` validates the
  shape regardless (`check_asset_entry`, url must be under `/media/`).
  Minimal wizard UI (file input + thumbnail strip) wired into the existing
  question-form step. Verified end-to-end with a real Playwright run: upload
  → resize/re-encode → served via `/media/` → thumbnail shown.

## Low priority / nice to have

- [x] **Cap / prune `UserTemplate` revisions.** `REVISION_RETENTION_LIMIT = 20`
  in `apps/editor/views.py`; each update prunes to the N most recent right
  after snapshotting. Covered by `tests/test_user_templates.py`.
- [x] **CI pipeline** running ruff, pytest, the Node test, and a Docker build
  (`.github/workflows/ci.yml`, Postgres 16 service, uv + Node setup). Repo is
  now a git repo (`main` branch, local); push to GitHub to activate it.
- [x] **Per-object rate limiting** on the AI transform endpoint. Verified
  already true: DRF's `ScopedRateThrottle.get_cache_key` keys on
  `request.user.pk` when authenticated, so it was already per-user, not one
  shared bucket for the whole scope. Added
  `test_rate_limit_is_isolated_per_user` to lock the guarantee in.
- [ ] **Expand the CSS property allowlist** as real templates need it (kept
  intentionally tight in `sanitize.py`). Ongoing — several safe properties
  (`-webkit-font-smoothing`, `backdrop-filter`, `align-self`,
  `scroll-behavior`, `overflow-x`/`-y`, and others) were already added as
  the AI legitimately needed them; expect more.
- [x] **`styles.rules` gained no `@media` support.** Turned out
  `editor-core.js`'s `buildCss()` already rendered `styles.mediaQueries`
  (dead code, never populated) — and it was completely unvalidated on the
  Python side, a latent CSS-injection gap (an AI response or a manual
  UserTemplate save could smuggle arbitrary text into a raw
  `@media ${query} { ... }` string). Fixed both at once:
  `document_validation.py` now validates `styles.mediaQueries` (allowlisted
  query string via new `check_css_media_query`, nested rules reuse the same
  `{selector, declarations}` checks as top-level rules); the wizard styles
  prompt now tells the AI it can use it, optionally, for real breakpoints;
  `apps/editor/rendering.py`'s thumbnail renderer stays consistent. Scope
  note: this only covers the wizard's full-document generation — the
  editor's incremental AI-transform has no per-declaration operation type
  for media queries, so that path is unchanged (out of scope here).
- [ ] **Extract a shared SSE/reasoning-display module.** `template-wizard.js`
  deliberately duplicates `editor-ai.js`'s SSE-parsing and typing-bubble
  logic instead of extracting it, to avoid risking a regression in the
  working in-editor assistant under time pressure (see the `ponytail:`
  comment at the top of `template-wizard.js`). Worth extracting into a
  shared module if a third consumer of this logic shows up.
- [x] **Structured request logging / metrics** for AI usage and error rates.
  `apps/ai_assistant/usage_logging.py` logs one logfmt line
  (`ai_usage scope=... user=... outcome=... duration_ms=...`) per SSE request
  across all 4 AI endpoints (transform + 3 wizard views), greppable/parseable
  without a new metrics dependency. Bonus: the wizard views had the same
  uncaught-exception gap as the transform 500 fix above — added the same
  `except Exception` catch-all there too, each covered by a test.

## Done (Unreleased)

- [x] AI-guided template wizard (`/wizard/`): chat kickoff, dynamic question
  form, review/clarification loop, two-phase document generation
  (structure then styles), save via existing `/api/user-templates/`.
  "En blanco" base template removed in favor of this flow.
- [x] Streaming AI responses: SSE `event: reasoning` chunks + terminal
  `done`/`error`, live sentence-by-sentence reasoning display in both the
  editor assistant and the wizard.
- [x] Two-role AI model split (conversational model for chat-shaped calls,
  main model for heavy structured generation) — editor's instruction
  clarification pass and all three wizard calls.
- [x] `AnthropicMessagesProvider` for opencode.ai models routed via
  `/v1/messages` (MiniMax, Qwen3.7 family) instead of chat/completions.
- [x] `document_validation.py` — full-document validation with strict
  structural key checks at every nesting level; `json-repair` fallback for
  malformed AI JSON.
- [x] `body_outline` in the edit-transform payload so global-mode AI edits
  target real current indices instead of guessing.
- [x] Base vs user templates: `/home/` (base `Template`) and `/gallery/`
  (per-user `UserTemplate`), both Postgres, seeded base catalog.
- [x] Save as template (Crear / Actualizar) via `POST/PATCH /api/user-templates/`,
  owner-scoped; green "☆ Guardar" button + modal.
- [x] Version history + rollback: `UserTemplateRevision` auto-snapshot on update;
  Historial UI with Restaurar + Eliminar; no-op saves don't pad history.
- [x] Server-side template loading: `json_script` seed + external
  `seed-loader.js` (external because CSP `script-src 'self'` blocks inline).
- [x] Modal-based editing UI: `#elementModal` (inspector + structure) and
  `#sectionModal` (Contenido/Diseño/SEO/JSON); preview now full-width.
- [x] Floating action bar (Editar / Duplicar / Eliminar) on the selected element.
- [x] Automatic global mode (checkbox hidden; follows selection) + `@element`
  chip + click-outside-to-deselect + collapsible "Ver más" op list.
- [x] PostgreSQL for local dev via the repo `compose.yaml`.
- [x] AI fill fix (`background` shorthand over gradients); `AI_MAX_OPERATIONS`
  raised 20 → 50; CSS allowlist gained `border-top/right/bottom/left`.

## Done (0.1.0)

- [x] Device Authorization flow end to end (code / activate / token / refresh).
- [x] AI transform endpoint with input sanitizer + operation validator.
- [x] Swappable provider interface with fake + OpenAI implementations.
- [x] Editor split into template + static without breaking existing behavior.
- [x] AI panel: connect, select, generate, preview, apply (single undo), discard.
- [x] Projects API, owner-scoped (no IDOR), with revisions.
- [x] pytest + Node test suites green; ruff clean; Docker + Compose.
