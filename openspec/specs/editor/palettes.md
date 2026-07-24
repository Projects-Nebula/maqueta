# Capability: template palettes

**Status:** implemented and verified. This specification is the source of
truth for the active color palette stored in a template and the reusable,
owner-scoped `UserPalette` catalog.

The implementation lives in `apps/editor/palettes.py`, the editor and wizard
templates/scripts, the `UserPalette` model/API, the AI document/operation
validators, and the server-side renderers. The contract is designed to add
palette provenance without adding a second rendering source of truth or
requiring a migration of legacy JSON.

## Requirement: Preserve one rendering source of truth

The system SHALL render the four semantic palette roles from these variables:

- `--color-primary`
- `--color-background`
- `--color-text`
- `--color-surface`

`styles.palette` SHALL be optional metadata containing exactly `id`, `name`,
and `source` (`preset`, `custom`, or `ai`). It SHALL never duplicate color
values. Other existing design variables (font, width, radius, and spacing)
remain valid outside the bounded palette contract.

#### Scenario: Legacy state remains compatible

- WHEN a template has no `styles.palette` metadata
- THEN it loads, edits, exports, thumbnails, previews, and publishes using its
  existing `styles.variables` without an automatic rewrite
- AND the editor presents it as a legacy/custom palette until the user makes a
  palette change
- AND matching color values alone SHALL NOT infer preset provenance

#### Scenario: Palette metadata is validated on write

- WHEN a client, project, user template, or AI submits `styles.palette`
- THEN the server accepts only a safe slug matching
  `^[a-z0-9]+(?:-[a-z0-9]+)*$`, at most 64 characters
- AND `name` MUST be a non-empty string of at most 80 characters
- AND `source` MUST be one of `preset`, `custom`, or `ai`
- AND all four palette variables MUST be present and six-digit hex colors
- AND a `preset` id and its four values MUST match the server catalog exactly
- AND additional metadata keys MUST be rejected

## Requirement: Provide a single preset catalog

The system SHALL define the role labels and generic preset catalog once on the
server in `apps/editor/palettes.py`. `palette_catalog_for_client()` SHALL
inject the same JSON catalog into `/editor/` and `/wizard/`; JavaScript SHALL
not maintain a second list of preset colors.

The shipped catalog is:

| ID | Name | Primary | Background | Text | Surface |
| --- | --- | --- | --- | --- | --- |
| `ocean` | Océano | `#0f766e` | `#f0fdfa` | `#134e4a` | `#ffffff` |
| `forest` | Bosque | `#166534` | `#f0fdf4` | `#14532d` | `#ffffff` |
| `sunset` | Atardecer | `#c2410c` | `#fff7ed` | `#431407` | `#ffffff` |
| `neutral` | Neutro | `#475569` | `#f8fafc` | `#0f172a` | `#ffffff` |
| `high-contrast` | Alto contraste | `#facc15` | `#050505` | `#ffffff` | `#111111` |

Presets SHALL use descriptive names and SHALL not copy third-party logos,
fonts, or complete protected brand identities.

#### Scenario: Editor and wizard use the same catalog

- WHEN a logged-in user opens `/editor/` or `/wizard/`
- THEN the page receives the same server-generated roles and presets
- AND the client uses that injected catalog for labels, descriptions, and
  swatches

## Requirement: Configure palettes in the editor

The Design panel SHALL show a preset selector, active name, four color
swatches, a description, the existing four color controls, and the existing
typography/dimension controls. A preset application SHALL atomically update
the four variables and metadata, refresh the preview, emit the normal
`vjpb:state-committed` autosave signal, and create exactly one undo entry.

The user SHALL be able to name and edit a custom palette. Valid edits are
stored in the template state. Palette mutation is synchronous; success and
reset feedback are immediate, while the existing autosave flow persists the
committed state.

#### Scenario: Apply and undo a preset

- WHEN the user selects a preset
- THEN the preview and state expose all four catalog values and preset metadata
- AND one Undo returns the complete previous palette

#### Scenario: Custom palette feedback

- WHEN the user enters a valid name and four valid hex colors
- THEN the state uses `source: "custom"` and survives a save/reload
- WHEN a color is not six-digit hex
- THEN the color is not committed and an accessible error live region is
  shown
- WHEN the user resets the palette
- THEN the initial palette snapshot is restored with one undoable change

## Requirement: Provide an owner-scoped reusable palette catalog

The system SHALL persist reusable palettes in `UserPalette`, scoped by the
authenticated owner. Each entry SHALL contain a stable owner-scoped slug, a
name, and exactly the four validated semantic role values. The API SHALL
expose owner-scoped CRUD at `/api/user-palettes/`; list, detail, update, and
delete operations SHALL never return or mutate another user's entries.

The editor SHALL inject the current user's catalog into the same palette JSON
used by presets. Applying a saved entry SHALL copy its values into
`styles.variables` and record only `{id, name, source: "custom"}` in
`styles.palette`. Saving and deleting entries SHALL use the authenticated
session and CSRF protection. The wizard SHALL offer the same saved catalog,
and the server SHALL resolve a selected custom slug through `request.user`
before deterministic generation.

#### Scenario: Save, reuse, and delete a palette

- WHEN a user saves four valid role colors with a name
- THEN one owner-scoped `UserPalette` is created with a unique stable slug
- AND the editor can apply it to the current template and the wizard can use
  it as the deterministic generation palette
- WHEN the user deletes the saved entry
- THEN it disappears from that user's catalog without changing another user's
  entry

#### Scenario: Cross-owner access is denied

- WHEN user B requests, updates, or deletes a palette owned by user A
- THEN the API responds as if the object does not exist
- AND user B's editor and wizard catalog never contains user A's palette

## Requirement: Communicate contrast accessibly

The editor SHALL report contrast for text/background and primary/surface
controls. It SHALL warn when the recommended WCAG AA thresholds are not met,
without silently changing the user's colors. Contrast feedback SHALL be visible
at 320px and 390px and exposed through a live region. Invalid input errors and
contrast warnings SHALL use distinct feedback tones.

## Requirement: Constrain wizard and AI palette changes

The wizard SHALL allow the user to select a catalog preset or an owner-scoped
saved palette before generation. When selected, `WizardAIService` SHALL apply
that palette exactly on the server and SHALL skip the AI style-color call so
the model cannot overwrite the choice. Without a selection, the style result
SHALL be normalized to exactly the four palette variables and metadata with
`source: "ai"`.

Incremental AI `set_style_variable` operations SHALL accept only the four
known role names and six-digit hex values, independently of the provider.
Whole wizard documents SHALL pass the same palette metadata/variable checks
before being returned to the browser.

## Requirement: Preserve palette through persistence, export, and rendering

JSON downloads SHALL include active variables and optional metadata. HTML
downloads, gallery thumbnails, live preview, and published pages SHALL render
the active variables; metadata SHALL not produce visible or executable markup
of its own. User-template and project serializers SHALL validate palette state
on write, while legacy state without metadata remains accepted.

#### Scenario: Persist and render a custom palette

- WHEN a valid custom palette is saved to a user template and loaded again
- THEN its metadata and four variables are unchanged
- AND thumbnail/public rendering uses the variables without rendering metadata
  as page content

## Verification

The implementation is covered by:

- `tests/test_palettes.py` for catalog, metadata, hex, operation, and document
  validation;
- `tests/test_user_palettes.py` for CRUD, stable slugs, owner isolation, and
  editor catalog injection;
- `tests/test_user_templates.py` and `tests/test_editor_rendering.py` for
  persistence, legacy compatibility, and server rendering;
- `tests/test_wizard_service.py` and `tests/test_ai_wizard.py` for deterministic
  preset application and request validation;
- `tests/e2e/editor_ux.spec.js` for preset/undo/custom/error/contrast/wizard
  flows at desktop and 320px; saved-palette API and wizard-resolution paths
  are covered by Django tests.

The completed repository gate passed 251 PostgreSQL pytest tests, Ruff,
Django checks, the Tailwind build, Node tests, and 15 Playwright tests.

## Out of scope for this version

- Scraping external sites for palettes.
- Copying logos, fonts, or complete protected brand identities.
- Unlimited Tailwind variables without a semantic role and validation need.
