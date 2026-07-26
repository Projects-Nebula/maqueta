# UXUI.md — UI/UX audit and continuous-improvement instructions

This is a review of the actual frontend in this repository, not a generic
checklist. Findings are based on the current templates, CSS, JavaScript, and
real browser verification. Re-read and update it whenever a new frontend
surface, modal, form, or storefront flow is added.

## 1. Executive verdict — 2026-07-24

The frontend has a solid visual base and the audited behavior pass is now
implemented. Cross-page design tokens remain centralized, the editor's
selection/action-bar interaction is preserved, and the former interaction
defects are covered by focused tests and real-browser verification.

The template palette pass is also implemented: the Design panel now exposes a
server-backed preset and owner-scoped reusable catalog, custom four-role
editing, contrast feedback, and single-step undo while preserving legacy
templates without `styles.palette`. The editor and wizard now share the same
SSE/reasoning client instead of carrying two parsers.

This was intentionally a **behavior/accessibility pass**, not another broad
visual restyling. The completed scope includes quick-insert rendering, modal
keyboard/focus behavior, mobile editor density, shared async feedback, wizard
asset lifecycle, checkout/PayU edge states, auth sizing, authenticated
navigation, a visible editor exit route, and the new consent-gated analytics
dashboard. The historical findings below remain as an audit record; their
acceptance criteria are tracked as done in `BACKLOG.csv` rows 43, 48, and
52–66.

## 2. Scope and evidence

### Static review

Reviewed the server-rendered surfaces and their scripts/styles:

- `templates/editor/editor.html`, `template_wizard.html`, `home.html`, and
  `gallery.html`, and the server-backed palette catalog in
  `apps/editor/palettes.py`;
- `static/editor/editor.css`, `editor-core.js`, `editor-ai.js`,
  `save-template.js`, `template-wizard.js`, and `wizard.css`, plus the shared
  `static/shared/ai-stream.js` module;
- `templates/storefront/products.html`, `payment_config.html`,
  `success.html`, `checkout_cancel.html`, and `payu_redirect.html`;
- `static/storefront/products.js` and `payment-config.js`;
- `templates/analytics/dashboard.html` and `static/analytics/dashboard.js`,
  `dashboard.css`, and the public consent tracker;
- `templates/registration/login.html` and `signup.html`.

### Browser review — baseline audit

A real authenticated session was exercised with Chromium through the
project's Playwright image:

- public pages: `/login/`, `/signup/`, `/cancelado/`, and `/gracias/`;
- authenticated pages: `/home/`, `/gallery/`, `/productos/`, `/config/`,
  `/wizard/`, `/analytics/`, and `/editor/?t=landing`;
- public published-template consent UI plus authenticated dashboard at
  1440×900, 390×844, and 320×800;
- editor interactions: section modal, AI drawer, save modal, product-link
  modal, image-picker modal, Escape handling, and keyboard traversal.
- palette interactions: preset apply/undo, custom name/color editing, contrast
  warning, reusable palette save/apply/delete, wizard preset/saved selection,
  and 320px overflow behavior.

The existing selection and shared-token Playwright specs also passed. No
console errors, uncaught page errors, or failed requests were found in the
main 1440px audit, and the tested pages did not show horizontal overflow at
that width.

## 3. Prioritized gaps — historical findings

The following tables preserve the evidence and acceptance criteria from the
baseline review; they are not an open-work list. The completed status is
recorded in section 4 and in the corresponding `BACKLOG.csv` rows.

### P0 — fix before calling the editor complete

| Gap | Evidence | Where | Acceptance criteria |
| --- | --- | --- | --- |
| **[Resolved] Quick-insert presets rendered unstyled** | Baseline audit found that `sectionPreset()` emitted semantic classes such as `.hero`, `.container`, `.feature-grid`, `.cta-box`, and `.footer-row` after the Tailwind migration. This affected Hero, Beneficios, Texto, Imagen, Llamado, and Footer in the first editor content panel. | `static/editor/editor-core.js`; `BACKLOG.csv` rows 43 and 55 | Every preset has real, allowlisted Tailwind classes and is visually usable in the preview immediately after insertion. Add a browser regression for at least Hero, Image, and CTA. **Satisfied.** |
| **Dialog keyboard behavior is incomplete** | The section modal closes on Escape, but `saveTemplateModal`, `paymentLinkModal`, and `imagePickerModal` remain open after Escape. The focus can leave the section dialog after repeated Tab presses. There is no focus restoration to the opener. | `static/editor/editor-ai.js`; `static/editor/save-template.js`; `templates/editor/editor.html` | One modal manager owns open/close state; Escape closes whichever modal is open; focus is trapped while modal is open and returned to the trigger; backdrop and close buttons remain functional. |

These were functional/accessibility defects, not optional polish. They were
addressed before adding another modal-driven editor feature.

### P1 — high-impact usability and state feedback

| Gap | Evidence | Where | Acceptance criteria |
| --- | --- | --- | --- |
| **Mobile editor has too much command density** | At 390px the topbar actions wrap into multiple rows; the preview toolbar is crowded; the fixed `IA` FAB sits over the preview content. There is no horizontal overflow, but the layout is still difficult to scan and operate. | `templates/editor/editor.html`; `static/editor/editor.css` | Collapse low-frequency actions into an overflow/menu group, keep primary actions visible, make the preview toolbar wrap or simplify, and move the FAB so it never obscures editable preview content. Verify at 390px and 320px. |
| **Product management has silent or disruptive states** | Initial list failures are ignored; toggle/delete failures are not surfaced; create/upload failures use `alert()`; success has no in-page confirmation; buttons are not disabled while requests are running; native file inputs show browser-default English copy inside the Spanish UI. | `templates/storefront/products.html`; `static/storefront/products.js` | Add loading, empty, success, and error regions with `aria-live`; disable the active action while pending; replace `alert()` with the shared feedback pattern; provide a localized upload control and selected-file name. |
| **Payment configuration lacks transaction feedback** | The page renders eight long repetitive gateway cards. Save failures use `alert()`; successful saves silently rerender; there is no saving/disabled state, rollback when a save fails, test-connection action, or concise help for sandbox versus production credentials. | `templates/storefront/payment_config.html`; `static/storefront/payment-config.js` | Show per-card saving/saved/error state, preserve unsaved values on failure, make the real/fake distinction explicit, and add progressive disclosure or grouping so the page is scannable. |
| **Wizard asset lifecycle is incomplete** | Images can be added up to 20 and previewed, but there is no remove action, no visible file type/size guidance, and no cancel/restart/abort path for a long SSE request. The generated “Nombre del template” input has a label without an associated `for`/`id`. | `templates/editor/template_wizard.html`; `static/editor/template-wizard.js`; `static/editor/wizard.css` | Each uploaded asset can be removed before generation; upload constraints are visible; the user can cancel/restart; the submit state is recoverable; every dynamic control has an accessible name. |
| **Initial wizard input is unnamed** | Browser audit found the visible `textarea#wizardInput` as the only unnamed interactive control on the tested pages. Placeholder text is not a reliable accessible label. | `templates/editor/template_wizard.html` | Add a visually hidden label or `aria-label`, and keep the name present in the initial, loading, error, and retry states. |
| **Editor feedback is too ephemeral and not semantic** | `showToast()` dismisses after roughly 2.3 seconds, has no success/error variants, and `#toast` has neither `role="status"` nor `aria-live`. Several actions therefore feel like no-ops when a toast is missed. | `static/editor/editor-core.js`; `static/editor/editor.css`; `templates/editor/editor.html` | Use one feedback component with semantic live-region behavior, visible success/error/instruction variants, an appropriate timeout, and a non-time-based way to review important errors. |

### P2 — consistency, discoverability, and edge surfaces

| Gap | Evidence | Where | Acceptance criteria |
| --- | --- | --- | --- |
| **Tabs and device switcher expose visual state only** | `.tabs button` has no `role="tab"`, `aria-selected`, or `aria-controls`; device buttons use only the `active` class and have no `aria-pressed`. | `templates/editor/editor.html`; `static/editor/editor-ai.js`; `static/editor/editor.css` | Implement correct tab/button semantics and keep DOM state synchronized with the visual state. |
| **Modal semantics are only partially complete** | Dialogs have `role="dialog"` and `aria-modal`, but headings/descriptions are not linked with `aria-labelledby`/`aria-describedby`; `#aiDrawer` lacks `aria-modal`; focus restoration is absent. | `templates/editor/editor.html`; `static/editor/editor-ai.js` | Every dialog has a programmatic title/description, correct modal state, a labelled trigger where applicable, and focus restoration. |
| **Checkout result states are too sparse** | `/gracias/` tells a pending buyer to refresh manually and has no retry/status polling; `/cancelado/` has no route back to the store or page. At 390px `/gracias/` measured 426px wide because the fixed card width is combined with padding under content-box sizing. | `templates/storefront/success.html`; `templates/storefront/checkout_cancel.html` | Make the card fluid (`max-width` plus `box-sizing`), expose pending status accessibly, provide a retry/continue action, and give cancellation a clear next step. |
| **Auth forms need narrow-width and password UX hardening** | Login/signup cards use fixed content-box widths; they will exceed viewports below their effective width even though 390px passed. Inputs lack `autocomplete` values and there is no password visibility/help affordance. | `templates/registration/login.html`; `templates/registration/signup.html` | Use fluid card sizing and `box-sizing`, add `username`/`current-password`/`new-password` autocomplete, and associate errors with their fields. |
| **Storefront pages still duplicate component styling** | Products and payment config each define their own button, card, radius, and warning colors; raw status colors remain even after token consolidation. | `templates/storefront/products.html`; `templates/storefront/payment_config.html`; `static/editor/editor.css` | Extract only the genuinely shared feedback/card/button primitives and map status colors to documented tokens; retain local layout rules where they are intentionally different. |
| **Empty states and navigation are underpowered** | Gallery/home states leave large unused areas and do not consistently offer a primary create action or links to Products/Config. Navigation is fragmented across editor, gallery, products, and config. | `templates/editor/home.html`; `templates/editor/gallery.html`; storefront templates | Give each empty state one primary next action and provide a consistent authenticated navigation path. |
| **PayU redirect is a visual outlier** | `payu_redirect.html` is a bare paragraph plus an auto-submitting form, with no branded loading state, fallback action, or `<noscript>` message. It is a transitional page, but it is still visible when the redirect is delayed or scripting is blocked. | `templates/storefront/payu_redirect.html` | Add the shared tokens, a loading indicator, explanatory copy, fallback submit action, and a no-script fallback without exposing gateway credentials. |

## 4. Implementation status — 2026-07-24

The audit acceptance pass is complete. The implementation deliberately keeps
page-specific layout rules local while sharing semantic feedback, navigation,
tokens, and accessibility behavior where the surfaces have the same contract.

| Area | Delivered | Verification |
| --- | --- | --- |
| Quick-insert presets | Replaced legacy semantic preset classes with allowlisted Tailwind utilities and fixed the stale tab target. | Hero, Image, and CTA render in the preview through Playwright. |
| Editor dialogs and controls | Added one modal manager with Escape, backdrop close, focus trap/restoration, dialog naming, tab state, and device `aria-pressed`. | Editor browser regressions at desktop and 320px. |
| Editor exit navigation | Added a visible `Salir` link in the editor topbar that returns to the authenticated template gallery. | Browser regression verifies visibility, label, and `/gallery/` destination. |
| Mobile editor and feedback | Reduced topbar density, protected preview space from the AI FAB, and made toasts/live regions semantic. | Playwright overflow and drawer checks; Node and Django tests. |
| Products and payment configuration | Added loading/empty/success/error states, localized file controls, save preservation, shared navigation, and per-card status. | Django tests and browser UI suite. |
| Gateway credentials | Added owner-scoped `validate` actions for all eight gateways. It checks required stored fields and provider initialization without creating a checkout session or charge. | `tests/test_payment_config.py` (including missing credentials and owner isolation). |
| Wizard assets and requests | Added visible constraints, owner-scoped deletion, cancellation/restart, network recovery, and accessible dynamic fields. | Wizard upload/delete tests, Node tests, and browser suite. |
| Checkout, PayU, auth, and empty states | Made result cards fluid and actionable, added pending status/retry affordances, a PayU fallback/noscript state, autocomplete/error associations, and workspace navigation. | Responsive Playwright checks at 320px/390px plus Django checks. |
| Public analytics consent and dashboard | Added an opt-in banner, pseudonymous visitor cookie, bounded page/click/pointer events, responsive metrics/session controls, and normalized heatmap rendering. | `tests/test_analytics.py`, public-page rendering tests, and authenticated Playwright dashboard/320px checks. |
| AI editor on legacy saved pages | Selected nodes from pre-Tailwind documents can contain semantic classes such as `site-header`; the AI context now removes only those stale tokens while preserving strict generated-operation validation. | `tests/test_ai_transform.py` and `tests/test_tailwind_classes.py`; authenticated transform regression. |
| Template palettes | Added the server-backed Ocean/Forest/Sunset/Neutral/High Contrast catalog, owner-scoped reusable palettes with save/apply/delete controls, custom four-role HEX validation, accessible contrast/error feedback, atomic preset undo, wizard preset/saved context, and legacy-state compatibility. | `openspec/specs/editor/palettes.md`; `tests/test_palettes.py`, `tests/test_user_palettes.py`, `tests/test_document_validation.py`, PostgreSQL pytest gate, and Playwright palette/wizard tests at desktop and 320px. |
| Shared AI stream client | Extracted SSE buffering, terminal event collection, and live reasoning-bubble filtering into `static/shared/ai-stream.js`; editor and wizard retain surface-specific status copy only. | `tests/js/ai-stream.test.js`, Node test suite, and editor/wizard browser smoke flows. |

The remaining local colors and page-specific button rules are intentional
layout details, not a second token system. Future UI work should preserve the
shared primitives and the continuous-improvement rules below.

### Final verification

- `pnpm run build:css` completed with Tailwind v4.3.3.
- Ruff check and format check passed; `manage.py check` reported no issues and
  `makemigrations --check --dry-run` reported no changes.
- `AI_PROVIDER=fake uv run pytest` passed **251 tests** against the configured
  PostgreSQL service.
- Node tests passed, and the official Playwright image passed **15 browser
  tests**, including public consent-before-identification, dashboard empty
  states, the 320px layout, the AI transform regression on a legacy-class
  header, and the palette preset/custom/wizard flows.

## 5. What is already good — do not regress it

- `static/shared/tokens.css` is the single source of truth for cross-page
  palette, typography, radius, and shadow roles. Keep its names stable rather
  than adding page-local aliases.
- The main 1440px surfaces and the tested authenticated mobile pages are
  structurally responsive: the baseline audit found no console/page/request
  errors, and the final browser suite adds a no-horizontal-overflow check for
  `/login/`, `/signup/`, `/cancelado/`, `/gracias/`, and the editor at 320px.
- The editor selection highlight, hover outline, and floating contextual
  action bar form a coherent interaction pattern. Improve their mobile and
  keyboard boundaries; do not replace them without a measured problem.
- AI-generated content, deterministic quick presets, and product cards use
  coherent allowlisted Tailwind classes. Storefront management controls now
  expose explicit asynchronous feedback while retaining intentionally local
  layout rules.
- The preview iframe has a meaningful title and sandbox boundary, and the
  tested representative modal/drawer open flows do not produce browser
  console errors.
- Template colors have one source of truth: `styles.variables` renders the
  active four semantic roles, while `styles.palette` is bounded metadata. The
  preset catalog is server-owned and shared by editor and wizard.

## 6. Recommended delivery order

The ordered implementation pass above is complete. For future frontend work,
use the same order when a new surface introduces equivalent defects: first
make the primary interaction work, then make keyboard/mobile state behavior
explicit, then align cross-page feedback and edge states.

Do not start another token-renaming pass without a measured reuse problem; the
token layer is already adequate for future implementation slices. For template
colors, use `openspec/specs/editor/palettes.md` rather than reopening the
completed checklist that was removed from `TODO.md`.

## 7. Continuous-improvement rules

Before shipping any new page, form, modal, or storefront operation:

1. Reuse `static/shared/tokens.css`; do not add another page-level `:root`
   palette or a near-duplicate button/status system without documenting why.
2. Give every interactive element a programmatic accessible name and every
   stateful control a semantic state (`aria-selected`, `aria-pressed`, live
   region, or equivalent).
3. Define loading, empty, success, error, retry, and cancellation states
   before calling the flow complete. Never rely on `alert()` or a short toast
   as the only feedback for a state-changing operation.
4. For every dialog, verify close button, backdrop, Escape, Tab traversal,
   focus restoration, and the mobile viewport in a real browser.
5. Verify at least 1440px, 390px, and 320px widths for editor and management
   surfaces. A page with no horizontal scrollbar can still be too dense or
   have a fixed control covering content.
6. Update this file, the relevant `BACKLOG.csv` row, and a verified
   `learnings.jsonl` record after an audit or implementation changes the
   documented state.

## 9. Addendum — 2026-07-25

Three new interactive surfaces shipped after the 2026-07-24 pass, plus one
fix to the shared dialog manager itself (`BACKLOG.csv` rows 71–84, commit
history `34ba82d`..`decb316`):

- **`#htmlImportModal`** ("Pegar HTML") — added, then found (via this
  file's own rule 4, "verify close/backdrop/Escape/Tab/focus in a real
  browser") to never actually open at all: `EditorModals` kept a
  hand-maintained 5-modal array that this new modal was never added to.
  Fixed at the root, not just the missing entry — `EditorModals`
  (`editor-ai.js`) now discovers every `.panel-modal[role="dialog"]` by
  query at load instead of a hand-maintained list, so this class of bug
  can't recur for a future template-defined modal.
- **Command palette (`Ctrl/Cmd+K`)** — a JS-built overlay, not
  template-defined, so it needed one addition to the pattern above:
  `EditorModals.register(el)` for modals constructed after the one-time
  query already ran. Registered, gaining the same Tab-trap/Escape/
  focus-restore contract every other dialog has for free.
- **"Actividad" panel** in the save modal (owner-scoped AI/save audit
  trail) — read-only list, no new interaction pattern, no dialog of its
  own.

All 6 shared dialogs plus the command palette now have e2e coverage that
they open (`tests/e2e/editor_ux.spec.js`, `tests/e2e/command_palette.spec.js`)
— per rule 4, discovering `#htmlImportModal`'s dead-open bug live is exactly
why that rule exists, and it's now closed. No open P0/P1/P2 gap from this
addendum; nothing here reopens the historical tables in section 3.

## 8. Source-of-truth records

- `BACKLOG.csv` — prioritized work items and verification state.
- `learnings.jsonl` — proven technical findings only; never store secrets.
- `README.md` and `openspec/project.md` — project-level pointers and setup
  context.
