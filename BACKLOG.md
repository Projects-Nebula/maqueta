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
- [ ] **Validate `OpenAIProvider` against the real API.** Tests use the fake +
  mocks; the Responses API `text.format` json_schema shape may need adjustment
  for the installed SDK version once a real `OPENAI_API_KEY` is set.

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
- [ ] **Autosave projects.** Wire the editor to `POST /api/projects/{id}/revisions/`
  with debounce; persist `state` and reload on open.
- [ ] **Registration flow.** accounts app is prepared for it but signup is not
  implemented yet.
- [x] **Frontend test runner.** `npm test` runs `node --test tests/js/**/*.test.js`
  (`package.json`); wired into `.github/workflows/ci.yml`.
- [x] **Template thumbnails.** Server-side mini-render (`apps/editor/rendering.py`)
  walks `state.document.body` + `state.styles` into a standalone HTML doc, shown
  scaled 0.25x in a `pointer-events: none` `<iframe srcdoc>` on each gallery card
  (`templates/editor/home.html`, `gallery.html`). No new deps, no headless
  browser at request time. Falls back to the first-letter avatar when `state`
  is null/empty (e.g. `Template.state = None` uses the built-in default page).
  Verified with a real Playwright screenshot against a seeded template.
- [ ] **Image upload for the wizard.** Deliberately deferred to a second pass:
  let a user attach images while building a custom template, optimize them
  server-side (resize/compress, cap dimensions) so a heavy upload can't
  affect any other flow, and register them in `state.assets` for use in the
  generated page.

## Low priority / nice to have

- [ ] **Cap / prune `UserTemplate` revisions.** History grows unbounded per
  template; add a retention limit (keep last N) or a bulk "clear history".
- [x] **CI pipeline** running ruff, pytest, the Node test, and a Docker build
  (`.github/workflows/ci.yml`, Postgres 16 service, uv + Node setup). Note:
  repo has no `.git` yet — workflow is ready but won't run until pushed to
  GitHub.
- [ ] **Per-object rate limiting** on the AI transform endpoint (per user, not
  just per scope) for finer abuse control.
- [ ] **Expand the CSS property allowlist** as real templates need it (kept
  intentionally tight in `sanitize.py`). Ongoing — several safe properties
  (`-webkit-font-smoothing`, `backdrop-filter`, `align-self`,
  `scroll-behavior`, `overflow-x`/`-y`, and others) were already added as
  the AI legitimately needed them; expect more.
- [ ] **`styles.rules` gained no `@media` support.** The wizard prompt tells
  the AI not to attempt responsive breakpoints (it has no way to express
  them in the current flat `{selector, declarations}` shape) — add real
  nested/media-query support if responsive AI-generated pages matter.
- [ ] **Extract a shared SSE/reasoning-display module.** `template-wizard.js`
  deliberately duplicates `editor-ai.js`'s SSE-parsing and typing-bubble
  logic instead of extracting it, to avoid risking a regression in the
  working in-editor assistant under time pressure (see the `ponytail:`
  comment at the top of `template-wizard.js`). Worth extracting into a
  shared module if a third consumer of this logic shows up.
- [ ] **Structured request logging / metrics** for AI usage and error rates.

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
