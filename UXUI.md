# UXUI.md — UI/UX audit and continuous-improvement instructions

Written as a UI/UX review of the actual current state of this project (not
a generic checklist) — every finding below was verified by reading the
real templates/CSS in this repo, not assumed. Intended to be read by any
agent working on visual/UI changes here, and re-read/updated whenever a
new UI surface is added.

## 1. Current state: three unreconciled design languages

This is the single biggest, most concrete finding. The project currently
has THREE independent, drifted sets of design tokens for what should be
one visual identity:

1. **The editor app itself** — `static/editor/editor.css`'s `:root`:
   `--app-bg:#eef2f7`, `--panel-bg:#fff`, `--border:#dce3ec`,
   `--text:#172033`, `--muted:#657287`, `--primary:#5b5ce2`. Font: `Inter`
   (via whatever the page's own font stack resolves to — check
   `editor.css`'s `body` rule). This is the most polished, most consistent
   surface in the app — it's a real design system with `--radius`,
   `--shadow`, `--danger`, `--success` tokens all reused consistently
   across ~1200 lines.

2. **Storefront management pages** — `templates/storefront/products.html`
   and `templates/storefront/payment_config.html` each have their OWN
   inline `<style>` redeclaring a SIMILAR but not identical token set:
   `--bg:#f5f6fa` (not `--app-bg:#eef2f7`), `--surface:#fff`,
   `--border:#e2e4ec` (not `#dce3ec`), `--text:#182034` (not `#172033`),
   `--text-muted:#6b7080` (not `--muted:#657287`), `--primary:#5b5ce2`
   (this one matches). Font: `Inter, Arial, sans-serif`. **Note**:
   `payment_config.html` was written in this same working session and
   copied `products.html`'s drift forward instead of fixing it — a
   concrete example of how this kind of drift compounds if nobody
   consolidates it.

3. **Customer/account-facing pages** — `templates/storefront/success.html`,
   `templates/storefront/checkout_cancel.html`, `templates/registration/
   login.html`, `templates/registration/signup.html`: a THIRD inline style
   set, `font-family: system-ui, sans-serif` (not Inter at all),
   `background:#f5f6fb` (yet another near-miss of the same blue-grey).

**None of these three sets of tokens are shared from one file.** A brand
color change today would require editing at least 3 places (editor.css,
products.html, payment_config.html) and would still miss a 4th visual
language (success/checkout_cancel/login/signup) entirely.

## 2. Priority fixes (ranked by effort-to-impact)

1. **Extract one shared token stylesheet.** Create
   `static/shared/tokens.css` (or similar) with ONE `:root` block —
   editor.css's token set is the most mature, use it as the base
   (`--app-bg`, `--panel-bg`, `--border`, `--text`, `--muted`, `--primary`,
   `--radius`, `--shadow`, `--danger`, `--success`). Link it from every
   template that currently hand-rolls its own `:root` block
   (`products.html`, `payment_config.html`, `success.html`,
   `checkout_cancel.html`, `login.html`, `signup.html`) and delete the
   duplicated declarations from each. This is a pure CSS-variable-naming
   change — it does not require touching any Tailwind class or component
   markup, so it's low-risk and should be done FIRST, before any of the
   items below, so they inherit the fix instead of adding a 4th drifted set.
2. **Unify the font stack.** Pick one (`Inter` with a system fallback is
   already the editor's choice and the more deliberate one) and apply it
   project-wide via the same shared stylesheet, replacing every
   `system-ui, sans-serif` instance.
3. **Fix the still-broken quick-insert presets** (`BACKLOG.csv` row 43,
   found earlier this session): `static/editor/editor-core.js`'s
   `sectionPreset()` (Hero/Beneficios/Texto/Imagen/Llamado/Footer) emits
   semantic classes (`.hero`, `.container`, `.feature-grid`, `.cta-box`)
   that no stylesheet defines anywhere — every one of these renders
   completely unstyled today. This is the single most visible, most
   frequently-hit broken UI surface in the editor (it's the FIRST thing
   shown in "Contenido rápido") and should be a close second priority
   after the token consolidation above. Fix: give each preset real
   Tailwind utility classes, matching the pattern already established this
   session for the AI-generated product card (`apps/ai_assistant/
   prompts.py`'s product-card spec) — a card with padding, radius, shadow,
   spacing between children, not semantic class names with no backing CSS.
4. **Consolidate the modal system.** The editor alone has grown FIVE
   separate custom modals sharing one backdrop
   (`#elementModal`/`#sectionModal`/`#saveTemplateModal`/
   `#paymentLinkModal`/`#imagePickerModal`, all `.panel-modal`), each with
   its own close-button wiring duplicated in `editor-ai.js`
   (`editorClose`/`sectionClose`/`paymentLinkClose`/`imagePickerClose`, four
   nearly-identical `addEventListener("click", closeAllModals)` calls).
   This isn't broken, but it's the kind of duplication that will keep
   growing linearly with every new modal-driven feature (the payment-link
   and image-picker modals added this session already repeat the pattern
   twice). Worth extracting a tiny `bindModalClose(id)` helper the next
   time a 6th modal is added, not urgent enough to refactor proactively.
5. **Toast notifications are easy to miss** (found live this session,
   `static/editor/editor-core.js`'s `showToast`): a 2.3s auto-dismissing
   toast is the ONLY feedback for several non-obvious states (e.g.
   "Elegí un producto para insertar" when the product select is empty).
   A user testing "Insertar producto" without having created a product yet
   reported "nada pasó" — the toast fired but was easy to miss. Consider a
   slightly longer dismiss time for error/instructional toasts vs.
   confirmation toasts, or a distinct visual treatment (the current CSS
   likely doesn't differentiate error from success toasts — verify
   against `editor.css`'s `.toast`/`.toast.visible` rules before changing).

## 3. What's already good (don't "fix" these)

- `editor.css`'s token system itself (once extracted/shared, per #1 above)
  is well-structured: consistent radius/shadow/color-role naming, not ad
  hoc per-component values.
- The floating action bar (`editor-ai.js`'s `buildActionsBar`) and
  selection-highlight system (`__vjpb-selected`/`__vjpb-hover` in
  `installPreviewInteractionHandler`) are a genuinely polished, considered
  interaction pattern — drag-and-drop, hover outlines, and the contextual
  action bar all work together coherently. Don't rewrite this to "improve"
  it without a concrete, observed problem.
- The AI-generated content (product cards, this session's iframe embeds)
  already produces real, coherent Tailwind styling — the model is doing
  its job well within the allowlist it's given. The gap is specifically in
  the DETERMINISTIC/hand-written templates (presets, storefront pages),
  not the AI-driven content.

## 4. Continuous-improvement process for future agents

Before shipping ANY new template, page, or modal in this project:

1. **Reuse tokens, don't invent them.** If you're about to write
   `<style>:root { --something: #hex; }</style>` in a new template, stop —
   link the shared token stylesheet (see #1 above; if it doesn't exist yet,
   that's the first thing to create) instead of hand-rolling a 4th/5th
   variant. Grep for `--primary` or `--panel-bg` across `templates/` and
   `static/` before picking a new color name — if something close already
   exists, use it.
2. **Match the font stack already in use**, don't introduce
   `system-ui`/a new web font without a reason to reconsider the whole
   project's typography, not just one page.
3. **Before considering a UI change "done", verify it renders** — this
   project's own established discipline (see `AGENTS.md`/`CLAUDE.md`) is
   real browser verification via Playwright for any UI/behavior change,
   not just a visual guess from reading the template source. A broken
   preset like #2 above would have been caught immediately by actually
   looking at the rendered output instead of trusting the JSON structure.
4. **When you find a drift like this file documents**, don't silently
   perpetuate it (copy-pasting an existing template's inline styles is how
   `payment_config.html` added a 3rd near-duplicate variant this session)
   — either fix the shared source first, or explicitly flag the drift in
   your commit message/a BACKLOG.csv row the way this file does, so the
   next agent doesn't have to rediscover it from scratch.
5. **Re-run this audit's section 1 whenever a new template ships** —
   grep every `templates/**/*.html` for an inline `<style>` block
   containing `--` (a hand-rolled `:root`); if the count of independent
   token sets went up instead of down, the fix in #1 either wasn't applied
   or was bypassed.

## 5. Close-out note

This file is a point-in-time audit, not a living spec — once the token
consolidation (#1) and the broken presets (#3) are actually fixed, update
this document to reflect the new state (or fold the remaining open items
into `BACKLOG.csv` and delete this file, matching this project's own
close-out convention for root-level plan documents — see
`openspec/README.md`'s governance section). Do not let this file silently
go stale while the codebase moves on.
