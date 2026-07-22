# Capability: projects

Optional persistence of editor pages and their revision history. Code:
`apps/projects/`. Endpoints under `/api/projects/` (JWT/session required).

## Requirement: Owner-scoped project CRUD
The system SHALL expose `GET/POST /api/projects/`, `GET/PATCH/DELETE
/api/projects/{id}/`, scoped so a user only ever accesses their own projects.

#### Scenario: Create
- WHEN a user POSTs a project
- THEN it is created with them as owner and a UUID id

#### Scenario: No IDOR
- WHEN a user requests or modifies another user's project
- THEN respond 404 (existence not revealed)

## Requirement: Revisions
The system SHALL expose `GET/POST /api/projects/{id}/revisions/` recording the
JSON state, an auto-incremented version, a summary, and the change origin
(`manual` / `ai` / `import`).

#### Scenario: Create revision
- WHEN a revision is POSTed
- THEN it gets the next version number and records the acting user

#### Scenario: AI origin
- WHEN a revision is created with source `ai`
- THEN the stored revision reflects source `ai`

## Requirement: No implicit autosave
The system SHALL NOT persist on every keystroke; saving is explicit or debounced.
