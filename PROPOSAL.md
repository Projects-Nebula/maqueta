# PROPOSAL.md — Ideas from `corebunch/instatic` for maqueta

**Source:** https://github.com/corebunch/instatic (cloned locally, analyzed end-to-end)
**License:** MIT (David Babinec, 2026) — free to reuse code/patterns with attribution.
**What it is:** Self-hosted CMS + visual page editor. One Bun process (`Bun.serve`),
Postgres/SQLite behind a single `DbClient` interface, React 19 admin SPA (Vite),
a universal `data_tables`/`data_rows` content model, a `NodeTree<TNode>` page-tree
primitive, a plugin system sandboxed via QuickJS-WASM, a three-layer publish
pipeline, and an AI agent that edits pages via a browser/server tool bridge.

Architecturally it's a different stack (React/TS/Bun vs. our Django + vanilla
`editor-core.js`), so most of what follows is **borrow the pattern**, not
**copy the code**. Each item below states concretely what to build, where it
lands in maqueta, and how hard it is.

---

## 1. AI tool bridge: browser stays authority over live document state

**Instatic mechanism:** `server/ai/handlers/chat.ts` + `runtime/transport.ts`.
`POST /admin/api/ai/chat/:scope` opens an NDJSON stream. When the model wants
to call a browser-only tool (e.g. "insert this node"), the server emits
`{type:'toolRequest'}` over the stream instead of executing it itself. The
browser runs the tool against its own live store, then `POST
/admin/api/ai/tool-result` resumes the paused server-side tool loop with the
result. The server never mutates document state directly — it only runs the
model and routes tool calls; the client is the sole source of truth for the
live document.

**Why it matters for us:** today `EditorAIService`/`WizardAIService` compute
full operation lists server-side and the client applies them in one shot via
`EditorCore.commitProposal`. That's fine for single-turn edits, but it means
the AI never sees intermediate DOM state within a turn — it can't ask
"what does the page look like now" mid-generation without a whole new
request/response round trip.

**Concrete change:** Add a paused-stream + resume-endpoint pair to
`apps/ai_assistant`:
- `POST /api/ai/editor/transform/` keeps producing SSE as today, but can emit
  a new `event: tool_request` frame instead of `event: done`.
- New `POST /api/ai/editor/tool-result/` endpoint that resumes the same
  generation with the client-supplied result (validated same as any operation
  today, through `sanitize.py`/`operations.py` — no new trust boundary).
- `editor-ai.js` gains a small dispatcher: on `tool_request`, read live state
  from `editor-core.js` (already has `EditorCore.commitProposal`,
  `getNode`/`getParentInfo` — add read-only accessors), POST the result, keep
  listening on the same SSE stream.

**Difficulty:** medium. No React/Zustand needed — `editor-core.js` already
owns document state; this is purely an SSE contract change plus one new view.

**Status: deferred.** No concrete bug/limitation drives this today — it's a
speculative capability ("AI could see mid-generation state"), and it's the
riskiest item here because it adds a new paused/resumed state to the
security-critical AI streaming pipeline for a hypothetical benefit. Revisit
only when a real feature needs it; the design above is ready to build from
at that point.

---

## 2. Provider-agnostic AI driver: raw HTTP/SSE, no SDKs, one shared tool loop

**Instatic mechanism:** `server/ai/drivers/http/toolLoop.ts` — one
`runToolLoop()` drives the multi-turn tool loop for Anthropic, OpenAI,
OpenRouter, Ollama, or any OpenAI-compatible endpoint, via a small
per-provider `ProviderAdapter` (map history → request body, parse SSE →
common shape). No provider SDKs at all, enforced by an architecture test
(`ai-driver-isolation.test.ts`).

**Why it matters for us:** we already have 4 providers
(`OpenAIProvider`/`OpenCodeZenProvider`/`AnthropicMessagesProvider`/
`FakeAIProvider`) picked by `build_provider()` — same idea, but we do use the
`openai`/`anthropic` SDKs directly per provider. Adding a 5th provider (e.g.
raw Ollama, a local model, or a new OpenCode Zen model on a 3rd wire format)
currently means writing a new SDK-based class each time.

**Concrete change:** not urgent — our provider count is small and SDK-based
providers are working. Worth doing only if we expect to add several more
providers/endpoints; then a shared `ToolLoop` + thin `ProviderAdapter` per
provider (map to/from a common message shape, build headers, parse SSE)
reduces duplication across `providers.py`.

**Difficulty:** low-medium, pure backend refactor, no urgency.

---

## 3. Heavy-evidence elision in agent tool-loop history

**Instatic mechanism:** `toolLoop.ts`'s `HEAVY_TOOL_NAMES` / `stubHeavyResult`
— once a screenshot or full-page-HTML tool result is superseded by a newer
one in the same run, it gets stubbed to a one-line breadcrumb in the
conversation history sent back to the model. Keeps context bounded across a
long agent run without losing the latest state.

**Why it matters for us:** `EditorAIService`/`WizardAIService` send "selected
node + nearby context" per call (already minimal per our own convention —
"never send the full JSON document to the AI"), so this specific pressure is
lower today. But the wizard's multi-round review loop (`MAX_REVIEW_ROUNDS`,
up to 5) and the two-call generate flow do accumulate conversation history;
if a future feature keeps a running chat transcript with large payloads
(e.g. a full-page screenshot for visual QA), this pattern applies directly.

**Concrete change:** add a small helper in `wizard_service.py`/`service.py`
that, before appending a new tool/assistant turn to history, replaces any
earlier "heavy" payload (large HTML blob, image) with a short marker.

**Difficulty:** low. Worth doing opportunistically, not urgent given current
per-call payload discipline.

**Status: deferred, verified no trigger.** Checked `history` end-to-end
(`apps/ai_assistant/serializers.py`'s bounded `ListField`,
`template-wizard.js`'s `state.history`): every entry is a short text turn
(instruction/clarification/answer), never a screenshot or full document —
maqueta's own rule ("never send the full JSON document to the AI") already
prevents the class of payload this pattern targets. Nothing to elide today;
revisit only if a future feature starts attaching large payloads (e.g. a
screenshot-based visual QA step) to the history.

---

## 4. Three-tier sanitization split (value-level / block-level / rich-text)

**Instatic mechanism:** three separate, single-purpose sanitizers instead of
one monolith:
- `src/core/css-sanitize/sanitiseCssValue.ts` — CSS **value**-level: blocks
  `expression()`, `javascript:`, `{}` selector breakout, `</` RAWTEXT escape.
- A block-level `</style` neutralizer for raw `<style>` blocks.
- `src/core/sanitize.ts` (`sanitizeRichtext`/`sanitizeSvg`) — DOMPurify-based
  HTML sanitization, with a regex fallback stripper for code paths with no
  DOM runtime available.

Each is reused at every write site that touches that specific injection
surface (CSS injection is treated as a distinct attack surface from HTML
injection).

**Why it matters for us:** `apps/ai_assistant/sanitize.py` +
`tailwind_classes.py` already gate node structure and Tailwind class strings
(`is_allowed_tailwind_class`/`check_class_list`) — we don't hand-author raw
CSS values from AI output (styling goes through the Tailwind allowlist), so
the CSS-injection surface instatic worries about mostly doesn't exist for us
by design. The one place this is directly relevant: `styles.rules` /
`set_css_declaration` still exist for **legacy pre-Tailwind content**
(`openspec/project.md`'s gotchas section). If any AI or user-facing path can
still write into `styles.rules` values, a dedicated value-level sanitizer
(reject `expression()`/`javascript:`/selector-breakout patterns) closes that
surface explicitly rather than relying only on the CSS property allowlist.

**Concrete change:** audit whether `set_css_declaration`/legacy CSS write
paths in `operations.py` have an explicit value-content sanitizer (not just a
property-name allowlist). If not, add one small pure function, tested
directly against the injection patterns instatic lists.

**Difficulty:** low. Security-relevant — do this inline (per our own
CLAUDE.md rule: `sanitize.py`/`operations.py` are Opus-only, security-critical).

---

## 5. Encode non-obvious invariants as CI-enforced "architecture tests"

**Instatic mechanism:** `src/__tests__/architecture/*.test.ts` — 81 small
test files that assert structural/convention rules as real, CI-run unit
tests, not just docs or lint config: no hardcoded colors, no Tailwind,
capability-picker coverage, plugin-sandbox invariants, no Postgres-isms in
ANSI-SQL repositories, etc.

**Why it matters for us:** `openspec/project.md`'s "Non-obvious gotchas"
section is long and hard-won (CSP blocking inline scripts, `editor-core.js`
must never be refactored, `OPENAI_API_KEY` never reaching the frontend, the
iframe-embed three-places rule, Tailwind allowlist enforcement, the
`json-repair` document-corruption guard, etc.) — currently these are enforced
by convention + code review, not by an automated check that fails CI the
moment someone violates one.

**Concrete change:** add a small `tests/architecture/` (pytest) +
`tests/js/architecture/` (Node) suite that mechanically checks a few of the
highest-value invariants we already know are fragile:
- No inline `<script>` with executable JS in any template (grep-based test
  against `templates/`).
- `OPENAI_API_KEY` (or any provider secret) never appears in any
  `static/**/*.js` file or any DRF serializer output.
- Every Tailwind class literal in `apps/ai_assistant`/fixtures passes
  `is_allowed_tailwind_class` (catches the exact "safelist compiled a test
  fixture" bug already documented in our gotchas).
- `editor-core.js`'s original IIFE body byte-range is untouched except the
  facade (a checksum-ish guard, or at minimum "no diff outside the facade
  block" documented as a check).

**Difficulty:** low. Pure process improvement, no runtime code change,
directly prevents regressions we've already hit once (documented in our own
gotchas as "verified" past bugs).

---

## 6. Capability-string auth model instead of role strings

**Instatic mechanism:** `src/core/capabilities.ts` — 38 flat capability
strings are the sole access-control primitive; `requireCapability`/
`requireAnyCapability` gate every handler. Four system roles are just named
sets of capabilities, force-resynced from code on every boot so new
capabilities never strand existing accounts. Step-up re-auth (separate from
MFA) gates destructive actions with a configurable window; account lockout
uses one shared failure counter across password AND MFA attempts.

**Why it matters for us:** our auth today is mostly ownership-scoped
(`UserTemplate`/`UserPalette`/`Product`/`PaymentGatewayConfig` are all
owner-FK-scoped, no role system) rather than role/capability-based, because
there's currently one user tier. This becomes relevant only if/when maqueta
adds multi-role accounts (e.g. team members on one storefront, or an admin
role distinct from the owning seller).

**Concrete change:** not needed now — no current feature requires it. Flag
for later: if team accounts / shared storefronts are ever added, prefer a
flat capability-string model over ad-hoc role checks from the start.

**Difficulty:** medium, DRF permission-class work. **Deferred — no current
trigger.**

---

## 7. Static-bake + versioned in-memory cache for published pages

**Instatic mechanism:** three-layer publish pipeline — Layer A bakes fully
static pages to disk (atomic two-slot symlink swap, 0.6–1.4ms serves, zero
DB/render per request), Layer B is a versioned in-memory LRU keyed by
`(urlPath, canonicalQuery)` for anything not fully static, Layer C emits
per-node `<instatic-hole>` placeholders lazy-fetched client-side for
per-visitor dynamic content — a classifier auto-picks the layer per page,
authors never toggle anything.

**Why it matters for us:** `GET /t/<slug>/` (public template page) currently
re-renders via Django template + `rendering.py`'s `buildCss()` on every
request. Most published pages are static content (no per-visitor dynamic
holes) — full disk-bake (Layer A) assumes a page-tree/JSON render model
close to instatic's `NodeTree`, which is a bigger structural change than
warranted right now.

**Concrete change (the portable slice only):** adopt just Layer B —
a process-local versioned LRU cache in front of the public template render
(key: `(slug, gateway-state-if-any)`, invalidated by bumping a monotonic
"published version" integer on `Template`/`UserTemplate` save, not per
request). This is a caching strategy, not a new render pipeline: a
`functools.lru_cache`-style wrapper or Django's cache framework keyed by
`(slug, version)`, no Bun/React dependency.

**Difficulty:** high for the full 3-layer system (skip — assumes a
different document model), **low** for the LRU-cache-only slice. Recommend:
do the cache-only version if `/t/<slug>/` render cost ever shows up as a
real bottleneck; not urgent today (no reported latency problem).

---

## 8. QuickJS-WASM sandboxed plugin system

**Instatic mechanism:** third-party plugins run in a per-plugin `Bun.Worker`
hosting a QuickJS-WASM sandbox (no Node/Bun/fs/env by default, allowlisted
outbound network, heap/stack/eval-time limits enforced by a wall-clock
interrupt registry). A separate, non-sandboxed "editor.code" tier exists for
plugins that need full DOM access, gated behind one explicit dangerous
permission.

**Why it matters for us:** maqueta has no third-party plugin/extension
concept today. This is a large net-new subsystem, not an incremental change.

**Concrete change:** none now. **Only relevant if a plugin marketplace /
third-party extensibility becomes an explicit product goal** — flagging as
"not applicable today" rather than silently skipping it, per your
instruction not to skip anything.

**Difficulty:** high. Python has no QuickJS-WASM equivalent; would need
subprocess/pyodide/gVisor-style isolation to replicate. **Deferred — no
current trigger.**

---

## 9. CMS forms: challenge/submit flow + trust-only-the-published-snapshot

**Instatic mechanism:** `server/forms/handler.ts` — HMAC-signed page tokens
stamped into rendered forms, short-lived single-use challenges bound to
`(pageId, formId)`, honeypot + minimum-submit-time checks before validation,
per-IP and per-IP/form rate limits, body size caps before JSON parsing. The
server trusts only the published snapshot, never client-declared
field/table names.

**Why it matters for us:** maqueta doesn't currently have a generic
CMS-forms feature (storefront checkout is the closest analogue, and it
already never trusts client-supplied price — always re-reads
`Product.price_cents` from the DB, per our own gotchas). If a general
"contact form" / lead-capture module is ever added to the editor, this
challenge/submit pattern (HMAC page token + honeypot + rate limit + strict
field-name allowlist from the published document, not the request) is a
solid template to copy directly — it maps cleanly onto Django (signed
tokens via `django.core.signing`, DRF throttling classes for rate limits).

**Concrete change:** none now (no forms feature exists yet). Record as the
reference design for whenever a forms/lead-capture module is proposed.

**Difficulty:** low-medium, whenever that feature is scoped. **Deferred — no
current trigger, but concrete enough to build straight from.**

---

## 10. Audit log for AI/user edits

**Instatic mechanism:** `docs/features/audit-log.md`, `audit_events` table —
every mutating admin action is recorded (actor, action, target, timestamp).

**Why it matters for us:** the AI assistant applies operations that mutate a
user's saved page, and there is currently no record of *which* AI generation
or user action produced a given `UserTemplateRevision` — only the resulting
state snapshot exists (`apps/editor/models.py`'s
`UserTemplateRevision`, auto-snapshotted on real change). When something
looks wrong after an AI edit, there's no trail of "what instruction produced
this" to debug from — only `server.log`, which isn't queryable per-template
and isn't retained in the DB.

**Concrete change:** add an `AuditEvent` model in `apps/editor` (same
owner-scoped pattern as `Product`/`PaymentGatewayConfig`): `owner` FK,
`action` (`CharField` choices: `ai_transform`, `ai_wizard_generate`,
`template_save`, `palette_apply`, `revision_restore`), `target_type`/
`target_id`, `metadata` (`JSONField` — e.g. the instruction text, the applied
operation count), `created_at`. Write one row from
`EditorAIService.stream_generate_operations` after a successful apply and
from `UserTemplateViewSet`'s save/restore paths. Surface it as a read-only
list in the save modal's existing "Historial" panel (`save-template.js`),
next to the revision list it already renders.

**Difficulty:** low. One new model + migration, a few insert calls at
existing write sites, one read-only serializer/view. No new trust boundary
— it's owner-scoped like everything else, and only ever written server-side
after validation already passed.

**Status: done.** `AuditEvent` model (`apps/editor/models.py`, migration
`0009_auditevent`), owner-scoped read API at `GET /api/audit-events/`, write
sites in `UserTemplateViewSet.perform_create/perform_update`,
`EditorTransformView`, and `WizardGenerateView`. Final action set:
`ai_transform`, `ai_wizard_generate`, `template_create`, `template_save` —
`palette_apply`/`revision_restore` dropped, since palette apply is purely
client-side (no server round-trip to hook into) and restore already goes
through the same PATCH `perform_update` writes `template_save` from.
Surfaced as an "Actividad" panel in the save modal next to "Historial".
Tested in `tests/test_audit_log.py` + one assertion added to
`tests/test_ai_transform.py`.

**Known gap, fixed (`PLAN.md` step 2).** `AuditEvent` had no retention
policy — grew unbounded, storing AI instruction text indefinitely, unlike
`UserTemplateRevision` (`REVISION_RETENTION_LIMIT`) and `apps/analytics`'s
`purge_analytics`. Closed with Option A from `PLAN.md`: a new
`AuditEvent.record()` classmethod creates the row then prunes that owner's
events to `RETENTION_LIMIT = 100` — self-enforcing, no scheduling
dependency, same inline-prune shape `UserTemplateRevision` already uses.
All three write sites switched from `AuditEvent.objects.create` to
`AuditEvent.record`; the read API's slice now references
`AuditEvent.RETENTION_LIMIT` instead of a separate duplicated constant.
Tested in `tests/test_audit_log.py::test_record_prunes_to_retention_limit_per_owner`.

---

## 11. Media workspace: folders + blurhash placeholder

**Instatic mechanism:** `docs/features/media.md` — folders, pluggable
storage adapters, BlurHash placeholder generation (off-thread), usage
tracking (which pages reference which asset).

**Why it matters for us:** `apps/editor/models.py`'s `UploadedAsset` is
already close to this (owner-scoped, resized/re-encoded server-side via
`image_processing`) but is flat (no folders) and has no blurry placeholder —
today the `<img>` in the live preview and on a published page has nothing to
show while the real file loads, and there's no "what pages use this image"
view before deleting one.

**Concrete change (two independently-shippable slices):**
- **Blurhash placeholder:** generate a tiny blurhash string at upload time
  (the `blurhash` PyPI package, pure Python, no native deps) in
  `image_processing.py` alongside the existing resize step, store it on
  `UploadedAsset` (`blurhash = models.CharField(max_length=64, blank=True)`),
  decode it client-side to a CSS gradient/canvas placeholder in
  `editor-core.js`'s image-node renderer while the real `src` loads.
- **Usage tracking / folders:** lower priority — would need a
  `UploadedAsset` ↔ `UserTemplate` many-to-many derived from scanning
  `state.assets` on save, and a `folder` FK. No current pain point reported
  for this half; **defer it**, ship blurhash alone first.

**Difficulty:** low for blurhash (self-contained, one new field, one
render-path change). Medium for folders/usage-tracking — **defer that half,
no current trigger** (asset count per owner is small; a flat list hasn't
been reported as a problem).

**Status: blurhash slice done, substituted with a one-pixel average color.**
A full blurhash decode needs a JS DCT decoder, and `static/editor/*.js` has
no build step to vendor one into — a one-pixel average color
(`image_processing.py`'s `_dominant_color_hex`, Pillow-only, no new
dependency) gets the same "don't show a blank box while it loads" outcome
with a one-line client-side `background-color` instead. `UploadedAsset`
gained `placeholder_color`; applied in the wizard's upload thumbnail strip
(`template-wizard.js`) and the editor's saved-image picker
(`editor-core.js`). Folders/usage-tracking half stays deferred, no trigger.
Tested in `tests/test_wizard_upload.py`.

---

## 12. HTML import: paste external markup into the document tree

**Instatic mechanism:** `docs/features/html-import.md`, `@core/htmlImport`
— pastes/imports raw HTML, converts it into the page's node tree through the
same pipeline the AI's `site_insert_html` tool uses, so imported content is
sanitized identically to AI-authored content.

**Why it matters for us:** today the only way content enters a maqueta page
is: AI-generated operations, the wizard's full-document generation, or
manual editor UI actions (quick-insert presets, product insert). There's no
way for a user to paste in an existing snippet (e.g. an embed code they got
from elsewhere, or markup copied from another tool) without hand-building it
node-by-node in the editor UI.

**Concrete change:** add an `html_to_nodes(html: str) -> dict` function in
`apps/ai_assistant` (Python's stdlib `html.parser` or a small allowlisted
tag/attribute walk — no need for a heavy HTML5 parser given the output must
already pass the same `sanitize_node` gate as everything else), feeding
straight into the existing `sanitize_node`/`add_node` operation path — so
imported content gets **exactly** the same validation as AI-authored
content, zero new trust boundary. Expose it as a small "Pegar HTML" action
in the editor UI, client-side sends the raw string to a new
`POST /api/ai/editor/import-html/` endpoint (non-AI, synchronous, no SSE
needed) that returns a sanitized node ready to `add_node`.

**Difficulty:** medium — mostly in getting the tag/attribute mapping right
(inline styles → nothing, since maqueta is Tailwind-only; class list must
still pass `is_allowed_tailwind_class`, so imported markup with arbitrary
classes gets those classes stripped, which needs to be communicated to the
user, not silently dropped). Genuinely useful, not currently blocked by
anything — **no trigger to defer on**, but sequence it after items #4/#5
land, since it's new sanitizer-adjacent surface and should get the same
scrutiny.

**Status: done, with one simplification.** `apps/ai_assistant/html_import.py`
(`html_to_node`, stdlib `html.parser`) drops `class`/`style` entirely rather
than trying to map them through the Tailwind allowlist — a class-by-class
partial-preservation pass was more complexity than the feature warranted;
dropping them outright is simpler, always safe, and the response's
`skipped_attributes` count tells the client so it can say so, not silently
change the paste. New `POST /api/ai/editor/import-html/`
(`html_import` throttle scope, 20/m), "Pegar HTML" button + modal in
`editor.html`, `static/editor/html-import.js`. Tested in
`tests/test_html_import.py`.

**Honest scope note, addressed (`PLAN.md` step 3).** The original
all-or-nothing drop undersold its UX cost — pasting any styled snippet
produced completely unstyled output. Added `STYLE_TO_TAILWIND`, a small
(10-entry) allowlisted table of exact `(property, value)` matches
(`text-align`, `font-weight`, `font-style`, `text-decoration`), each still
re-validated through `is_allowed_tailwind_class` before being kept —
deliberately NOT a general CSS-to-Tailwind converter, only known exact
matches, to avoid reintroducing the "partial-preservation path that gets
subtly wrong" risk this item originally avoided. Raw `class=` is still
always dropped. `skipped_attributes` now counts only what's actually still
dropped after mapping. In-UI copy updated to describe the new partial
behavior. Tested in `tests/test_html_import.py` (mapped, unmapped, and
`class`-still-dropped cases).

---

## 13. Command palette (⌘K / Ctrl+K) for the editor

**Instatic mechanism:** `docs/features/spotlight.md` — a keyboard-driven
command palette to jump between pages/actions without mouse navigation.

**Why it matters for us:** pure editor-UI ergonomics, no backend
implications. `editor-core.js` already has a full command surface
(`getNode`/`getParentInfo`/`updateAll`, quick-insert presets, undo/redo via
`commitProposal`) that today is only reachable through the panel UI.

**Concrete change:** a small self-contained addition to `editor-ai.js` (or a
new `static/editor/command-palette.js`, loaded like `autosave.js`): a
`keydown` listener for `Ctrl/Cmd+K`, an overlay `<div>` with a filtered list
built from a static command registry (quick-insert presets, "guardar",
"deshacer/rehacer", "abrir historial"), dispatching to the same functions
the panel buttons already call. No new CSP surface (external file, no
inline script), no server involvement at all.

**Difficulty:** low. Pure frontend, no security surface, no new endpoint.
**Nice-to-have, not currently requested** — worth doing opportunistically
if editor UX work is already in flight, not worth a dedicated cycle on its
own.

**Status: done.** `static/editor/command-palette.js`, entirely self-built
DOM (no template markup needed), dispatches to the always-available topbar
buttons (Guardar/Deshacer/Rehacer/Pegar HTML/Importar/Descargar/Copiar) —
scoped down from the full quick-insert-preset registry originally proposed,
since those buttons live inside a modal with state dependencies that would
need their own investigation; the topbar actions are simpler and always
safe to dispatch. Verified live in a real browser via
`tests/e2e/command_palette.spec.js` (open/filter/Escape, run-a-command).

**Debatable call, resolved (`PLAN.md` step 4).** Investigated the presets'
modal-state dependency by tracing `editor-core.js`'s `[data-preset]` click
handler: it only reads `button.dataset.preset`, mutates `state`, and
toggles CSS classes on already-existing DOM elements (`setActiveTab`) —
nothing requires `#sectionModal` to be visually open, and `.click()` fires
the listener regardless of visibility. Widened `command-palette.js`'s
registry with all 6 presets (Hero/Beneficios/Texto/Imagen/Llamado/Footer),
dispatched by CSS selector instead of `id` (`run()` generalized to support
both). Verified live: inserting Hero from the palette with the section
modal closed the whole time renders the same styled section as the
existing modal-driven flow (`tests/e2e/command_palette.spec.js`).

**Round-2 `REVIEW.md` gap, fixed:** the palette originally hand-rolled its
own open/close instead of using the shared `EditorModals` system every
other editor dialog uses, so it had neither Tab-trapping nor
focus-restore-to-trigger. Fixing this surfaced a real, separate,
pre-existing bug: `EditorModals` kept a hand-maintained array of exactly 5
modal ids, and `htmlImportModal` (item #12) was never added to it —
**clicking "Pegar HTML" silently did nothing**, undetected by any existing
test. Root cause fixed, not just the missing entry: `modalElements` is now
built by querying every shared-class modal element once at load (closes
this bug class for any future template-defined modal), plus a new
`EditorModals.register()` for JS-built modals like the palette. Verified
live: `htmlImportModal` opens correctly, Escape restores focus to the
triggering element, Tab stays trapped inside the palette.

---

## Documentation sync gap (from `REVIEW.md`)

**Status: fixed (`PLAN.md` step 1).** `README.md`'s API endpoint list
documented `/api/ai/editor/transform/` and `/api/ai/wizard/*` but was never
updated for the two endpoints added in items #10/#12 — everything else
(`openspec/specs/`, `CHANGELOG.md`, `BACKLOG.csv`, `learnings.jsonl`) was
kept in sync as each item shipped, `README.md` was the one missed. Its
request-flow narrative now documents `POST /api/ai/editor/import-html/` and
`GET /api/audit-events/` alongside the existing AI endpoints.

---

## 14. MCP connector: expose maqueta as an MCP server

**Instatic mechanism:** `docs/features/mcp-connectors.md` — instatic itself
is exposed as an MCP server (`@modelcontextprotocol/sdk`), so any MCP
client (an IDE agent, a chat client) can drive the CMS as a set of typed
tools.

**Why it matters for us:** would let an external agent (e.g. this very
Claude Code session, in a different project) drive maqueta's editor
programmatically — read/write templates, trigger AI generation — instead of
only through the browser UI. Interesting but speculative: no current
workflow needs "an external agent controls maqueta," and it would require
exposing a new authenticated API surface equivalent in power to the full
editor UI (i.e. the same operations pipeline, but reachable without a
browser session).

**Concrete change:** none proposed now. If ever pursued: a thin MCP server
process (Python `mcp` SDK) authenticating via a scoped API token (not the
session cookie — a new, narrower credential), exposing tools that map 1:1
onto the *existing* validated operation pipeline (`operations.py`,
`sanitize.py`) — never a new, less-validated write path.

**Difficulty:** high, and **speculative — deferred, no current trigger**.
Same YAGNI reasoning as items #1/#3: don't build a new authenticated
surface for a use case nobody has asked for yet.

---

## 15. Dashboard widgets — not applicable, no current equivalent

**Instatic mechanism:** `src/core/dashboard/registry.ts` — a 12-column
widget grid on the CMS's landing page, with plugin-contributed widgets.

**Why it doesn't map cleanly:** maqueta has no "CMS home/dashboard" screen
— `/home/` and `/gallery/` are template *pickers* (grids of template
cards), not an analytics/status dashboard. The closest existing equivalent
is `apps/analytics/dashboard.html` (the analytics app's own dashboard),
which already serves that role for its specific domain (visitor/session
metrics), not a general widget system.

**Concrete change:** none. Recording this explicitly as **not applicable**
rather than silently skipping it, per your instruction not to skip
anything — there is no generic "landing dashboard" in maqueta for a widget
system to extend, and building one solely to host widgets would be
building a feature to justify a feature.

---

## What's explicitly NOT transferable, and why

- **Entire React 19 + Zustand+Mutative + CodeMirror + dnd-kit admin/editor
  stack, CSS Modules design system, in-house router.** Maqueta is
  intentionally vanilla-JS (`editor-core.js`, never to be "cleaned up" per
  our own CLAUDE.md) served via Django templates. Porting any editor UI code
  is a rewrite, not a port.
- **Bun-specific runtime primitives** (`Bun.serve`, `Bun.Worker`,
  `bun:sqlite`, `Bun.sql`, `Bun.$`, `Bun.build`). None exist under
  Django/gunicorn; the plugin sandbox host is built entirely on Bun worker
  semantics.
- **QuickJS-WASM plugin sandbox as a literal implementation** —
  `quickjs-emscripten` has no Python equivalent; already covered in item 8.
- **The whole `NodeTree<TNode>` + module-registry render pipeline.** Assumes
  a JSON page-tree document model with per-module pure `render()` functions.
  Our editor produces HTML/JSON directly against Django templates; adopting
  this wholesale means redesigning the page representation, far beyond
  "borrow a pattern."
- **TypeBox-as-JSON-Schema-for-AI-tools and the zod ban.** TypeScript-
  ecosystem specifics. The underlying principle (validate at every untyped
  boundary) already exists in our stack via DRF serializers +
  `jsonschema`/`document_validation.py` — no library change warranted.
- **Core Framework design-token engine** (fluid type/spacing scales,
  auto shade generation) — a commercial product instatic vendors in.
  Tailwind (which we already use) solves the same class of problem
  differently; not worth reimplementing.

---

## Recommended priority order

All actionable items are implemented, including every follow-up
`REVIEW.md` found and `PLAN.md` sequenced. Status by item:

1. **#4 CSS value-sanitizer audit** — **Done.** `sanitize.py`'s
   `CSS_VALUE_FORBIDDEN` now blocks `<>{}` breakout, tested in
   `tests/test_sanitize.py`.
2. **#5 Architecture-as-tests** — **Done.** `tests/test_architecture.py`;
   caught and fixed a real live bug along the way: `payu_redirect.html`'s
   inline `<script>` was silently CSP-blocked, moved to
   `static/storefront/payu-redirect.js`.
3. **#10 Audit log** — **Done, retention gap closed.** `AuditEvent` model +
   `GET /api/audit-events/` + "Actividad" panel; `AuditEvent.record()` now
   prunes to `RETENTION_LIMIT = 100` per owner (`PLAN.md` step 2).
4. **#11 Blurhash placeholder (media, slice 1)** — **Done, substituted**
   with a one-pixel average color (no JS decode library needed) —
   `UploadedAsset.placeholder_color`. Folders/usage-tracking slice stays
   deferred.
5. **#12 HTML import** — **Done, with safe style mapping added.**
   `class` dropped outright; a small allowlisted `style`-declaration →
   Tailwind-class table now preserves common visual intent
   (`text-align`/`font-weight`/`font-style`/`text-decoration`) instead of
   discarding all styling (`PLAN.md` step 3). New
   `POST /api/ai/editor/import-html/` + "Pegar HTML" UI.
6. **#13 Command palette** — **Done, widened to quick-insert presets.**
   Topbar actions plus all 6 section presets, after verifying the presets
   don't actually require `#sectionModal` to be open (`PLAN.md` step 4).
   Verified live via `tests/e2e/command_palette.spec.js`.
7. **#1 AI tool bridge, #3 Heavy-evidence elision** — evaluated in depth,
   **deferred**: no concrete trigger exists today (verified, not assumed —
   #3's `history` payloads are already small text turns, nothing "heavy" to
   elide).
8. **#7 (LRU-cache slice only)** — do if/when `/t/<slug>/` render cost is
   ever measured as a real problem; not urgent today.
9. **#2, #6, #8, #9, #11 (folders/usage-tracking slice), #14, #15** —
   deferred or not applicable, no current trigger; recorded here so they're
   not re-discovered from scratch later.
