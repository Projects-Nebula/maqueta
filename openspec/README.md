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
- `specs/editor/` — editor shell + AI panel integration (session + CSRF auth).

## Starting a session

Read `project.md`, then the relevant `specs/<capability>/spec.md`, then check
`changes/` for anything in flight. `BACKLOG.md` (repo root) lists what is next.
