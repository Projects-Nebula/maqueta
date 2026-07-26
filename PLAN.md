# PLAN.md — Execution order for `PROPOSAL.md`'s remaining work

**Status: converged after 4 rounds** (`BACKLOG.csv` rows 77–83). Round 5's
`REVIEW.md` found nothing actionable after specifically checking several
different areas, not just re-slicing the same angle — see its "why stop
here" section. Kept as the record of the ordering rationale across all
rounds, not a live to-do list.

Source: `PROPOSAL.md` (15 items, instatic-derived) + `REVIEW.md` (honest
gaps found reviewing items #10–#13 after they shipped). This plan only
covers what's actually actionable now — items with no current trigger
(#1, #2, #3, #6, #7, #8, #9, #11's folders slice, #14, #15) stay deferred,
not resequenced here.

## Ordering principle

Smallest-blast-radius-first, security/data-integrity before UX, "fix what
we shipped" before "ship something new." A gap in something already live
outranks a brand-new feature, regardless of original proposal numbering.

## Order

### 1. README endpoint sync (5 min) — **done**
**Why first:** zero risk, zero design decisions, purely mechanical, and
leaving docs stale gets worse the longer it waits.
**How:** add `POST /api/ai/editor/import-html/` and `GET /api/audit-events/`
to `README.md`'s existing endpoint list, same one-line style as the entries
already there. No code changes, no tests needed.

### 2. `AuditEvent` retention policy (small, do next) — **done, Option A**
**Why second:** the one real inconsistency-with-existing-conventions gap
from `REVIEW.md` — unbounded growth of a table that stores user-authored
text (AI instructions) with no purge path, unlike every other retained-data
model in this codebase (`UserTemplateRevision`, `apps/analytics`). This is
data-hygiene debt on something already shipped; close it before building
more on top of the same model.
**How — pick ONE, don't build both:**
- **Option A (row cap per owner, same shape as `REVISION_RETENTION_LIMIT`):**
  in `UserTemplateViewSet`/`EditorTransformView`/`WizardGenerateView`'s
  `AuditEvent.objects.create(...)` call sites, after creating, prune to the
  most recent N per owner. Simplest, no new command, no cron/schedule
  dependency — consistent with how `UserTemplateRevision` already does it
  inline.
- **Option B (age-based purge command, same shape as `purge_analytics`):**
  new `purge_audit_events` management command, `AUDIT_EVENT_RETENTION_DAYS`
  setting, run on a schedule (matches the analytics precedent, but adds an
  operational dependency — someone has to actually schedule it, which
  `apps/analytics`'s own docs already flag as a manual step).
- **Recommendation:** Option A. It self-enforces with no scheduling
  dependency, matches the closer precedent (`UserTemplateRevision`, not
  `apps/analytics`, since `AuditEvent` is per-owner operational data, not
  aggregate analytics), and is a 5-line change per call site.
**Test:** one test asserting the cap holds after N+1 creates, mirroring
`test_revision_history_is_capped_at_retention_limit` in
`tests/test_user_templates.py`.

### 3. HTML import: safe inline-style → Tailwind mapping (fast-follow) — **done**
**Why third, not second:** real UX limitation, but not a regression or a
data-hygiene problem — the current all-or-nothing drop is safe and honestly
labeled in the UI, just weaker than ideal. Lower urgency than #1/#2.
**How:** in `apps/ai_assistant/html_import.py`, add a small, explicit,
allowlisted mapping table (e.g. `text-align: center` → `text-center`,
`font-weight: bold`/`700` → `font-bold`) checked against
`is_allowed_tailwind_class` before being added to the node's `class` list —
never freeform CSS-to-Tailwind translation, only exact known-value matches.
Anything not in the table stays dropped (today's behavior), so this is
additive, not a rewrite. Update `skipped_attributes` semantics to only
count what's *still* dropped after mapping.
**Test:** extend `tests/test_html_import.py` with cases for each mapped
style value and confirm unmapped values still drop silently-but-counted.
**Scope guard:** keep the mapping table small (5–10 entries) and resist
scope creep toward a general CSS-to-Tailwind converter — that's a much
bigger, riskier feature this proposal never asked for.

### 4. Command palette: widen beyond topbar actions (optional, lowest priority) — **done**
**Why last:** explicitly a "nice-to-have" in the original proposal, and
`REVIEW.md` flagged the scoped-down version as a debatable-not-wrong call.
No urgency, no data-hygiene angle, purely UX polish.
**How — this one needs investigation before implementation, not straight
to code:** the quick-insert presets (`data-preset="hero"` etc.) currently
only work from inside `#sectionModal`'s open state. Before wiring them into
the palette:
1. Trace whether `insertPreset`-equivalent logic in `editor-core.js` can
   run independent of the modal being open (read-only investigation).
2. If yes: add those commands to `command-palette.js`'s registry, same
   dispatch-by-click pattern already used for topbar actions — but calling
   the underlying insert function directly instead of `.click()`ing a
   button that may not exist in the DOM when the modal is closed.
3. If no (modal state is load-bearing): either open the modal
   programmatically first, or leave this deferred — don't force it.
**Test:** extend `tests/e2e/command_palette.spec.js` with one case per
newly-reachable command.

**Outcome:** step 1 confirmed the presets don't need the modal open —
`.click()` fires the listener regardless of visibility, and the handler
only touches `state` plus CSS classes on elements already in the DOM. Went
straight to option 2: widened the registry (dispatch generalized to
selector, not just `id`), verified live in the Playwright container.

## What's explicitly NOT in this plan

Everything in `PROPOSAL.md` marked "deferred, no current trigger" (#1, #2,
#3, #6, #7 unless render cost becomes measured, #8, #9, #11's
folders/usage-tracking slice, #14, #15) stays deferred. Nothing here
resurrects them — they're documented, not forgotten, and should only move
when a real trigger shows up (a reported bug, a concrete feature request),
same standard already applied when they were first evaluated.

---

## Round 2 — from `REVIEW.md`'s review of the round-1 fixes

**Status: done.** One real gap, two explicitly-not-actionable items. Fixing
the one real gap surfaced a second, more severe bug (`htmlImportModal`
never opened at all) that no test had caught — see the outcome note below
step 1 and `BACKLOG.csv` row 81.

### 1. Wire the command palette into `EditorModals` (only actionable item) — **done**
**Why:** `command-palette.js` built its own overlay instead of using the
shared `EditorModals` contract every other editor dialog uses
(`#elementModal`, `#sectionModal`, `#saveTemplateModal`,
`#imagePickerModal`, `#htmlImportModal`, the AI drawer) — so it has neither
Tab trapping nor focus restoration to the triggering element on close. This
is a regression below a bar this exact codebase already set for itself
(`BACKLOG.csv` row 56), not a missing nice-to-have.
**How:** `EditorModals.open(modal, triggerEl)` / `EditorModals.closeAll()`
(`static/editor/editor-ai.js`) expect a modal element already in the DOM
with the app's standard dialog structure/classes — `command-palette.js`
currently builds `#commandPaletteOverlay` fresh on first open via JS, not
from template markup. Two viable approaches:
- **(a) Register the built overlay with `EditorModals` after building it**
  — call `EditorModals.open(overlay, triggerEl)` instead of the palette's
  own `open()`/`close()`, once `buildOverlay()` has run. Keeps the
  self-built-DOM approach, reuses the shared focus/Tab logic.
- **(b) Add `#commandPaletteOverlay` as real template markup** in
  `editor.html` (matching the other modals' pattern) and drop the
  DOM-building code entirely. More consistent with every other modal in
  the codebase, larger diff.
**Recommendation:** (a) — smaller diff, keeps the "no template markup
needed" property that made this feature cheap to add, while actually
closing the accessibility gap. Only fall back to (b) if `EditorModals`
turns out to assume something about static markup that a JS-built overlay
can't satisfy (verify this before committing to (a)).
**Test:** extend `tests/e2e/command_palette.spec.js` with a focus-restore
case (assert the previously-focused element regains focus after Escape)
and a Tab-trap case (assert Tab cycles within the overlay, doesn't reach
elements behind it).

**Outcome:** went with (a) — `EditorModals.register()` added, the palette
now calls `EditorModals.open()`/`closeAll()`. While implementing, checking
*why* (a) would even work exposed the actual mechanism: `modalElements` was
a hand-maintained array of exactly 5 ids, built once. Registering the
palette as a 6th entry would have worked, but it left the same fragile
pattern in place for the *next* new modal. Live-verifying the fix (per this
session's own standard: never trust "the code looks right" for a UI
change) caught that `htmlImportModal` — added in a previous round, never
manually added to that array — had the exact same problem already, silently,
with zero test coverage catching it. Fixed the pattern itself: `modalElements`
is now a one-time query for every shared-class modal (covers all
template-defined modals, present and future) plus `register()` for
JS-built ones. This is the same shape of finding this whole loop keeps
producing: a fix verified functionally correct still needs to be checked
against the codebase's own established patterns, not just against what it
was asked to do.

### 2. NOT planned: wrap `AuditEvent.record()` in a transaction
`REVIEW.md` flagged this as low-severity and consistent with an existing
accepted pattern (`UserTemplateRevision`'s prune logic has the same
non-atomic shape). Fixing it here would mean also fixing the older,
identical pattern to stay consistent — out of scope for what was actually
reviewed. Not resurrected without a concrete trigger (e.g. a real observed
over-count), same standard as every other deferred item.

### 3. NOT planned: `!important`/whitespace handling in `STYLE_TO_TAILWIND`
Explicitly called out in `REVIEW.md` as "not worth the added complexity
for a 10-entry table." Adding CSS-value normalization here is exactly the
scope creep `PLAN.md` step 3 already guarded against once — resist it
again.

## Sequencing rule

Do these one at a time, full quality gate (`ruff check`, `ruff format
--check`, `AI_PROVIDER=fake pytest`, `manage.py check`,
`makemigrations --check --dry-run`, `pnpm test`, and a live-browser pass
for #4) after each — same discipline as the first round, not a batch at
the end. Update `PROPOSAL.md`'s status blocks and `BACKLOG.csv` as each
one lands, same as before.

---

## Round 3 — from `REVIEW.md`'s review of round 2's fix

**Status: done.** One item.

### 1. Add permanent e2e coverage for `elementModal` and `paymentLinkModal` opening
**Why:** `REVIEW.md` found these two high-traffic modals had zero e2e
coverage — round 2 rewrote the shared infrastructure both depend on
(`editor-ai.js`'s `modalElements`), and the only reason a regression there
was ruled out was a throwaway verification script, not the permanent
suite. Small, mechanical fix — selectors already known from that
verification.
**How:** promote the two throwaway specs into
`tests/e2e/editor_ux.spec.js` (matches where the other modal-opening
assertions already live): select a preview node → click the "Editar"
floating-action-bar button (`[aria-label="Editar"]`, scoped inside
`#previewFrame`, since the button's visible text is only the glyph, the
label lives in `aria-label`/`title`) → assert `#elementModal` visible;
double-click a link/button node in the preview → assert `#paymentLinkModal`
visible.
**Test:** the tests themselves are the deliverable here — no separate test
of the tests.

**Outcome:** both promoted into `tests/e2e/editor_ux.spec.js`. Full 23-spec
suite green (was 21; +2). No regression found in either surface — the
value here was closing a coverage gap the review surfaced, not fixing a
new defect.

---

## Round 4 — from `REVIEW.md`'s review of round 3

**Status: done.** One item, same shape as round 3's.

### 1. Add permanent e2e coverage for `imagePickerModal` opening
**Why:** round 3 checked `elementModal`/`paymentLinkModal` but wasn't
systematic about `modalElements`' full membership — `imagePickerModal`
(double-click an `<img>` preview node) has the same dependency on the
round-2 shared-registry refactor and the same missing coverage.
**How:** verify live first (insert an image via quick-insert, close
`#sectionModal` first — it visually overlaps the preview and intercepts
the double-click otherwise — then double-click the image), then promote
into `tests/e2e/editor_ux.spec.js`.
**Outcome:** verified no regression, test promoted. All 6 `modalElements`
entries now have e2e coverage — see `REVIEW.md`'s coverage-status note for
the full list, so a future round doesn't need to re-derive it.
