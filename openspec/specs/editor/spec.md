# Capability: editor

Serves the visual editor and integrates the AI panel without breaking existing
behavior. Code: `apps/editor/`, `templates/editor/`, `static/editor/`.
The active template palette contract is defined separately in
`openspec/specs/editor/palettes.md`.

The editor and wizard consume the same server-injected palette catalog. The
palette specification is normative for `styles.variables`, optional
`styles.palette` metadata, legacy compatibility, persistence, rendering, and
AI validation; this editor capability spec covers the surrounding shell and
manual editing behavior.

## Requirement: Serve the editor
The system SHALL serve the editor shell at `GET /editor/` (login required),
split into a Django template + `editor.css` + `editor-core.js` + `editor-ai.js`
+ `seed-loader.js` + `save-template.js`, plus the shared
`static/shared/ai-stream.js` module. All executable page logic lives in
external `.js` files because the page CSP is `script-src 'self'` (inline
scripts are blocked); the injected template seed is inline
`type="application/json"` data only.

#### Scenario: Renders with wiring
- WHEN a logged-in user opens `/editor/`
- THEN the page references the static assets and the config endpoint (the AI
  transform URL), and sets the CSRF cookie via `ensure_csrf_cookie`
- AND it receives the server-backed palette catalog used by the Design panel

## Requirement: Templates and gallery
The system SHALL let a user start from a template. Curated base templates
(`Template`, global by `slug`) are listed at `GET /home/`; the user's own saved
templates (`UserTemplate`, owner-scoped) are listed at `GET /gallery/`. Both
pages require login and render their cards server-side. A card opens the editor
with the template's `state` already injected server-side (`?t=<slug>` for base,
`?ut=<id>` for the user's own), applied by `seed-loader.js` via
`EditorCore.commitProposal` — no client fetch.

#### Scenario: Open a base template
- WHEN a user clicks a card on `/home/`
- THEN `/editor/?t=<slug>` loads with that template's page as the initial state
- AND a null `state` (or unknown slug) falls back to the built-in default page

#### Scenario: User templates are private
- WHEN a user opens `/editor/?ut=<id>` for a `UserTemplate` they do not own
- THEN no state is injected (owner-scoped lookup); the default page loads

## Requirement: Save as template
The system SHALL let a logged-in user save the current editor `state` as a
`UserTemplate` via the `UserTemplateViewSet` API (session + `X-CSRFToken`,
owner-scoped, no IDOR). The "☆ Guardar" button opens a modal offering **Crear
nuevo** (POST, always available, requires a name) and **Actualizar** (PATCH,
offered only when the editor was opened from one of the user's own templates,
i.e. `?ut=<id>`). Base templates and fresh sessions get create-only.

#### Scenario: Create
- WHEN the user names and creates a template
- THEN a `UserTemplate` owned by the current user is created with the live
  `state`, and it appears on their `/gallery/`

#### Scenario: Update restricted to owner
- WHEN the editor was opened from `?ut=<id>` the user does not own
- THEN no `user_template_id` is exposed to the page and only "Crear nuevo" is
  offered (a PATCH to another user's template 404s via owner scoping)

## Requirement: Template version history and rollback
Updating a `UserTemplate` SHALL snapshot the state it replaces into a
`UserTemplateRevision` (owner-scoped), and only when the `state` actually
changes. The save modal SHALL list revisions with restore and delete, all
owner-scoped.

#### Scenario: Auto snapshot on change
- WHEN a `UserTemplate` is PATCHed with a different `state`
- THEN a new `UserTemplateRevision` captures the previous `state`
- AND a PATCH that does not change `state` (e.g. restoring the current version,
  or a name-only edit) creates no revision

#### Scenario: Restore and delete
- WHEN the user restores a revision from `GET /api/user-templates/<id>/revisions/`
- THEN its `state` is PATCHed back (itself snapshotted) and applied live via
  `EditorCore.commitProposal`
- AND deleting a revision (`DELETE …/revisions/<rev>/`) removes only that
  owner's revision (others 404)

## Requirement: Preserve existing editor behavior
The split SHALL keep all original features working: iframe element selection,
`selectedPath`, central `state`, undo/redo history, drag & drop, JSON
import/export, generated-HTML download, desktop/tablet/mobile preview,
structure and direct-JSON editing, and flicker-free preview updates.

#### Scenario: Works without AI
- WHEN the user never connects the AI
- THEN every manual editor function remains fully available

## Requirement: Modal editing UI
The editing controls SHALL be modals so the preview keeps the full width. A
floating action bar (Editar / Duplicar / Eliminar) appears on the selected
element; ✎ Editar opens `#elementModal` (inspector + structure), and the
preview toolbar opens `#sectionModal` (Contenido / Diseño / SEO / JSON). The
Duplicar / Eliminar buttons reuse the core's existing hidden `#duplicateButton`
/ `#deleteButton` handlers.

#### Scenario: Deselect on click-outside
- WHEN an element is selected and the user clicks empty preview space (outside
  any `[data-vjpb-path]` element and outside the action bar)
- THEN `EditorCore.clearSelection()` runs, the selection clears, the action bar
  disappears, and the context chip shows "no element selected"

## Requirement: AI panel
The system SHALL provide an "Asistente IA" panel with an instruction field,
generate/apply/discard controls, a loading indicator, readable errors, and a
summary of proposed operations (with the operation detail list collapsed behind
a "Ver más" toggle). Targeting is automatic: with no element selected it targets
the whole page (global mode, its checkbox hidden); selecting an element switches
to that element and shows an `@element` chip above the composer.

#### Scenario: Automatic global vs element target
- WHEN no preview element is selected
- THEN the request is sent in global mode (page summary as context)
- AND selecting an element switches the target to it (its node + nearby context)

#### Scenario: Same-origin session auth
- WHEN the panel calls `POST /api/ai/editor/transform/`
- THEN it uses the browser session cookie plus an `X-CSRFToken` header
  (no bearer token, no device flow); the endpoint requires an authenticated session

## Requirement: Share AI stream transport and reasoning display

The editor and wizard SHALL load `static/shared/ai-stream.js` before their
surface-specific scripts. The module SHALL own SSE block parsing, arbitrary
network-chunk buffering, terminal `done`/`error` collection, and the live
reasoning typing bubble. Each surface MAY provide its own status copy and
scroll callback, but SHALL NOT maintain a second SSE parser or typing-bubble
implementation.

#### Scenario: Editor and wizard consume the same stream contract

- WHEN either AI surface receives `event: reasoning` chunks followed by
  `event: done` or `event: error`
- THEN the shared module accumulates the reasoning text and returns the
  terminal payload to that surface
- AND chunk boundaries or a final block without a trailing separator do not
  discard a valid event

## Requirement: Deterministic apply, single undo
The frontend SHALL apply operations via `applyAIOperations(state, operations)`
with no `eval`, on a clone, previewing before commit.

#### Scenario: Apply
- WHEN the user applies a proposal
- THEN `flushHistoryCommit()` runs, the state is replaced, tree/inspector/JSON/
  preview update, and exactly one history snapshot is recorded
- AND the modified element stays selected if it still exists

#### Scenario: Discard
- WHEN the user discards a proposal
- THEN `state` is unchanged and no history entry is created

#### Scenario: Undo an AI change
- WHEN the user presses Ctrl/Cmd+Z after applying
- THEN the AI change is undone in a single step

## Requirement: No arbitrary code, no flicker
The system SHALL never let the AI generate or execute arbitrary JavaScript, and
SHALL update the preview in place (preserving scroll, focus, and `selectedPath`)
rather than reloading the iframe on every change.
