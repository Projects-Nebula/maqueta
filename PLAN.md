# PLAN.md — Execution record for `PROPOSAL.md`'s remaining work

**Status: converged, all committed and pushed to `main`.** Kept as a short
pointer to the ordering rationale and commit history, not a live to-do
list — the actual decisions are in the commit messages below, not repeated
here.

Source: `PROPOSAL.md` (15 items, instatic-derived) + `REVIEW.md` (honest
gaps found reviewing shipped items). Items with no current trigger (#1,
#2, #3, #6, #7, #8, #9, #11's folders slice, #14, #15) stay deferred —
documented in `PROPOSAL.md`, not resurrected here.

## Ordering principle

Smallest-blast-radius-first, security/data-integrity before UX, "fix what
we shipped" before "ship something new." A gap in something already live
outranks a brand-new feature, regardless of original proposal numbering.

## What shipped, in order

| # | Work | Commit |
| - | ---- | ------ |
| 1 | CSS value-sanitizer breakout fix | `34ba82d` |
| 2 | Architecture-as-tests + PayU redirect fix | `4ecbd98` |
| 3 | Owner-scoped audit log + retention | `a0f1757` |
| 4 | Upload thumbnail placeholder color | `ad0bea8` |
| 5 | Sanitized HTML paste import + style mapping | `d927c11` |
| 6 | Command palette + `EditorModals` dialog-discovery fix | `299f268` |
| 7 | `run-local.sh`/`setup.sh` non-interactive `pnpm install` fix | `e7f1200` |
| 8 | Documentation sync | `decb316` |

Each commit message states the "why" for that unit — read `git log` on
these hashes rather than this file for the reasoning.

## Explicitly not planned (found during review, deliberately skipped)

- `AuditEvent.record()`'s create+prune isn't wrapped in a transaction —
  low severity, matches an existing accepted pattern
  (`UserTemplateRevision`'s prune logic has the same shape). Revisit only
  on a real observed over-count, not speculatively.
- `STYLE_TO_TAILWIND` doesn't handle `!important`/whitespace variants —
  not worth the complexity for a 10-entry table; would reopen the exact
  scope creep guarded against when it was added.

## What's explicitly NOT in this plan

Everything in `PROPOSAL.md` marked "deferred, no current trigger" stays
deferred. Nothing here resurrects it — it's documented, not forgotten, and
should only move when a real trigger shows up (a reported bug, a concrete
feature request), same standard already applied when first evaluated.

---

## Current effort: gap analysis (2026-07-26)

Source: `PROPOSAL.md`'s 5-item evidence-based gap analysis. Order:
smallest-blast-radius/zero-risk first, security before new features,
blocked-on-external-access items sit out in `FYI.md` rather than stalling
the rest.

| # | Item | Decision |
| - | ---- | -------- |
| 1 | CI blocker close-out | Do first — trivial, zero risk |
| 2 | Login rate limiting | Before new features — security, no new dependency |
| 3 | Email infrastructure | Console backend (dev-safe default, same swappable-provider pattern as `AI_PROVIDER`); real provider is a deploy-time config decision, not a build blocker |
| 4 | Password reset | Blocked — Django's stdlib reset looks up users by email, but signup never collects one. Logged in `FYI.md`, partial build reverted rather than ship something that matches zero users. |
| 5 | Payment gateway live verification | Blocked — needs real sandbox credentials for 3 gateways, not a code decision. Logged in `FYI.md`, skipped this round. |
