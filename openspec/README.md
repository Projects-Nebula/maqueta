# OpenSpec

Spec-driven persistence so the project is continuable across sessions. This
directory is the durable contract; the code implements it.

## Structure

```
openspec/
  project.md              Session bootstrap: stack, layout, commands, conventions
  specs/<capability>/     Current behavior (source of truth), one dir per capability
    spec.md
  changes/                In-flight change proposals (not yet merged into specs)
    <change-id>/
      proposal.md         Why + what + impact
      tasks.md            Ordered implementation checklist
      specs/<cap>/spec.md Delta: ADDED / MODIFIED / REMOVED requirements
```

## Workflow (per change)

1. **Propose** — create `changes/<change-id>/proposal.md` + `tasks.md` + delta specs.
2. **Implement** — follow `tasks.md`; keep the quality gates in `project.md` green.
3. **Archive** — fold the delta into `specs/`, then remove the change folder.

## Spec format

Each requirement uses SHALL and at least one scenario:

```markdown
## Requirement: <name>
The system SHALL <behavior>.

#### Scenario: <case>
- WHEN <trigger>
- THEN <expected outcome>
```

## Capabilities

- `specs/ai-assistant/` — AI transform, sanitization, operation protocol.
- `specs/projects/` — project persistence + revisions.
- `specs/editor/` — editor shell, AI panel integration (session + CSRF auth),
  and the bounded template palette contract.
- `specs/analytics/` — consent-gated anonymous collection, owner-scoped
  reporting, heatmaps, and retention.

## Governance: when to use this flow vs. a root-level plan document

This project has used two different mechanisms for large changes so far —
know which one to reach for, and don't let a big feature land without
EITHER:

**Use the `changes/<change-id>/` flow above** for a change with a clear,
boundable scope you can fully spec before writing code — a new requirement
or two, a modification to existing behavior, something you can describe in
a handful of `## Requirement`/`#### Scenario` blocks before touching any
file. This is the default. Most changes belong here.

**Use a root-level plan document** (see the git history for `REFACTOR.md`,
`FEATURE.md`, `PAYMENTS.md` — all deleted after their close-out, never kept
around) only for something too large/exploratory to spec up front: a
multi-day, multi-phase build (e.g. a full CSS-architecture migration, a
brand-new capability with many external integrations) where the plan
itself needs to exist as a long-form document an agent executes end-to-end
without stopping, and where the exact shape of "done" gets refined while
building, not fully known before starting. These are NOT a replacement for
this directory — they are a bridge to it.

**The rule that must never be skipped**: a root-level plan document's own
close-out step MUST include writing (or updating) the relevant
`specs/<capability>/spec.md` here before the plan document is deleted. This
project got this wrong for its Tailwind migration and its whole storefront
build (both shipped via `REFACTOR.md`/`FEATURE.md`, closed out into
`CHANGELOG.md`/`BACKLOG.csv`/`learnings.jsonl` only — `specs/storefront/`
didn't exist until it was added retroactively, after the fact, during the
`PAYMENTS.md` multi-gateway work). Do not repeat that gap: `CHANGELOG.md`
answers "what shipped, when"; `BACKLOG.csv` answers "what's pending";
`learnings.jsonl` answers "what gotcha did we hit" — none of them answer
"what does this capability actually do right now, as a spec a future
change could delta against." Only `specs/` answers that, and only `specs/`
is checked before starting the NEXT change in the same area.

## Starting a session

Read `project.md`, then the relevant `specs/<capability>/spec.md`, then check
`changes/` for anything in flight AND `ls` the repo root for any stray
plan-in-progress document (a `*.md` file not in this list and not
`README.md`/`CLAUDE.md`/`AGENTS.md`/`CHANGELOG.md` at the root is almost
always one of these — read it before assuming it's stale). `BACKLOG.csv`
(repo root) lists what is next.
