# Changes

In-flight change proposals. Empty means no change is being worked on right now
(see `BACKLOG.csv` for what is queued).

## New change

Create `changes/<kebab-id>/` with:

- `proposal.md` — Why, What Changes, Impact.
- `tasks.md` — ordered `- [ ]` implementation checklist.
- `specs/<capability>/spec.md` — delta with `## ADDED`, `## MODIFIED`,
  `## REMOVED` requirement sections.

## Template — proposal.md

```markdown
# <change title>

## Why
<problem / motivation>

## What Changes
- <bullet list of changes>

## Impact
- Affected specs: <capabilities>
- Affected code: <apps / files>
```

On completion, fold the delta into `openspec/specs/` and delete the change folder.
