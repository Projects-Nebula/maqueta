# AGENTS.md — maqueta (Visual AI Editor)

Instructions for AI coding agents working in this repo. Tool-agnostic; for
Claude Code specifically, `CLAUDE.md` adds subagent delegation policy on top
of this. For stack, layout, commands, and non-obvious gotchas, see
`openspec/project.md` — read it first, this file is about **how to work**,
not what the project is.

## Setup

```bash
uv sync
npm install
npm run build:css                           # compiles static/editor/tailwind.css
docker compose up -d db                     # local PostgreSQL
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver           # http://localhost:8000/home/
```

`.env` is read once at process start (`environ.Env.read_env()` in
`config/settings/base.py`) — changing it requires a full server restart, the
autoreloader does NOT pick it up (it only watches `.py`/`.html`/`.js`).

Styling is Tailwind CSS (utility classes on `attributes.class`, see
`apps/ai_assistant/tailwind_classes.py`) — `npm run build:css` must be rerun
after changing the class allowlist there, since it regenerates the safelist
that drives the Tailwind CLI build. Needs Node 20+ (Tailwind v4).
`static/editor/tailwind.css` and `.tailwind-safelist.txt` are gitignored
build artifacts, never commit them.

## Before calling anything "done"

All of these must pass:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
node tests/js/apply.test.js
```

For UI/frontend changes, actually run the feature in a browser (or via a
direct API call with a real session — see below) before reporting success.
Passing tests verifies correctness of the code, not of the feature.

### Browser (Playwright) tests

`tests/e2e/` holds real-browser Playwright specs (`npm run test:e2e`) against
a running dev server (`BASE_URL`, default `http://127.0.0.1:8000`) and an
existing test user (`E2E_USERNAME`/`E2E_PASSWORD`). If the host is missing
Chromium's system libs (`libnspr4` etc.) and there's no passwordless sudo to
`playwright install-deps`, run it in the official image instead, from repo
root, with the dev server already running on the host:

```bash
docker run --rm --network host -v "$PWD":/work -w /work \
  mcr.microsoft.com/playwright:v1.61.1-jammy npx playwright test tests/e2e
```

Keep the image tag matched to the installed `@playwright/test` version
(`npx playwright --version`) — a mismatch fails the browser launch.

## Using learnings.jsonl

Before solving a problem:

1. Search `learnings.jsonl` for matches by error message, tags, project, and
   related files.
2. Prioritize learnings with `status: "verified"`.
3. Do not assume an unverified learning is correct.

After solving a problem:

1. Record only proven solutions.
2. Append a new JSON object on a single line.
3. Never store passwords, tokens, API keys, or private data.
4. If a solution replaces a previous one, use the `supersedes` field.

**Schema** (one JSON object per line, no wrapping array):

```json
{
  "id": "2026-07-22-01",
  "timestamp": "2026-07-22T14:30:00Z",
  "status": "verified",
  "title": "short title",
  "error_message": "the exact error string, if any, that led here",
  "cause": "verified root cause",
  "fix": "what actually resolved it",
  "tags": ["django", "pytest", "..."],
  "project": "maqueta",
  "files": ["apps/editor/views.py"],
  "supersedes": null
}
```

## Conventions

- **Python + dependencies via `uv` only** — never pip/poetry/pipenv.
- **Code, comments, identifiers, commit messages default to English.**
  User-facing app strings (login, editor panel, wizard chat) are Spanish to
  match the existing app.
- **Security is server-side and model-independent.** `sanitize.py` +
  `operations.py` are the single source of truth for what a node tree or AI
  operation may contain; `document_validation.py` is the same for a full
  AI-generated document. Never trust paths, nodes, operations, or a
  full document from the browser or the model — validate them the same way
  regardless of which AI provider produced them.
- **AI never returns free HTML.** Only the validated operation protocol
  (incremental edits) or a validated full document (the wizard) ever reaches
  the browser or gets saved.
- **Never expose provider API keys to the frontend.** Send the AI only what
  it needs (selected node + nearby context + design variables + instruction,
  or the wizard's description/answers) — never the full document.
- **One AI apply = one undo step** (`EditorCore.commitProposal`).
- Migrations are excluded from ruff — don't hand-edit an already-applied
  migration; write a new one.
- Do not "clean up" `static/editor/editor-core.js` — it's the original
  editor IIFE verbatim plus a facade appended inside it. See
  `openspec/project.md` gotchas before touching it.
- **Never trust client-supplied money amounts.** The checkout view
  (`apps/storefront`) always re-reads `Product.price_cents` from the DB —
  never a price/currency from the request. An `Order` is created by the
  signature-verified Stripe webhook for real payments; the fake-provider
  dev/test path is a deliberate, narrow exception — see
  `openspec/project.md`'s gotchas before changing either path.

## Testing AI-backed endpoints manually

The transform/wizard endpoints require an authenticated session; a fast way
to test one live without a browser:

```bash
DJANGO_SUPERUSER_USERNAME=tmp DJANGO_SUPERUSER_EMAIL=tmp@example.com \
  DJANGO_SUPERUSER_PASSWORD=tmp12345 uv run python manage.py createsuperuser --noinput
# log in with curl, keep the cookie jar, POST to the endpoint, inspect the SSE body
```

Delete the throwaway user afterward. These endpoints are SSE
(`event: reasoning` chunks, then a terminal `event: done`/`error`) — a plain
`curl -d ...` without `--no-buffer` will still work since curl reads the
full body from `-o` before you inspect it, but treat the response as an SSE
stream, not a single JSON blob, when parsing it.

## Related docs

- `openspec/project.md` — stack, layout, commands, non-obvious gotchas.
- `CHANGELOG.md` — what shipped.
- `BACKLOG.csv` — known limitations and pending work, structured for
  filtering (status/area/category/verification/blocked_by).
- `learnings.jsonl` — verified technical learnings from past debugging, one
  JSON object per line — check before starting, append after solving (see
  "Using learnings.jsonl" above).
- `openspec/specs/` / `openspec/changes/` — capability specs and in-flight
  change proposals.
