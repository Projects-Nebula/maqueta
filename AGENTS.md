# AGENTS.md — maqueta (Visual AI Editor)

Instructions for AI coding agents working in this repo. Tool-agnostic; for
Claude Code specifically, `CLAUDE.md` adds subagent delegation policy on top
of this. For stack, layout, commands, and non-obvious gotchas, see
`openspec/project.md` — read it first, this file is about **how to work**,
not what the project is.

## Setup

```bash
./setup.sh                                # interactive prerequisite/dependency bootstrap
./run-local.sh                            # starts PostgreSQL when configured and Django
./mockup.sh                                # destructive local reset + deterministic demo data
```

`setup.sh` asks before installing missing system requirements. Refusing a
required installation stops the setup without starting the server. It prepares
`.env`, Python/Node dependencies, Tailwind CSS, PostgreSQL, and migrations;
`run-local.sh` remains responsible for starting Django.

The workflow was verified on 2026-07-24 with
`UV_CACHE_DIR=/tmp/uv-cache ./setup.sh`: PostgreSQL was healthy, Tailwind
generated 30,184 classes, and Django reported no pending migrations. The
setup script still exits before starting the development server.

`mockup.sh` is a local-only destructive reset. It migrates first, flushes the
database and referenced media files, and seeds deterministic records for every
application model. It refuses `DEBUG=False` unless
`MOCKUP_ALLOW_NON_DEBUG=1` is explicitly provided. The seeded local login is
`demo` / `demo12345`. Optional credential overrides are documented as commented
`MOCKUP_USERNAME`, `MOCKUP_EMAIL`, and `MOCKUP_PASSWORD` entries in
`.env.example`; keep the non-development override commented by default.

Manual equivalent:

```bash
uv sync
corepack enable pnpm
pnpm install --frozen-lockfile
pnpm run build:css                           # compiles static/editor/tailwind.css
docker compose up -d --wait db              # local PostgreSQL (run-local.sh does this automatically)
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver           # http://localhost:8000/home/
# Optional scheduled cleanup for opt-in anonymous analytics:
uv run python manage.py purge_analytics
```

`.env` is read once at process start (`environ.Env.read_env()` in
`config/settings/base.py`) — changing it requires a full server restart, the
autoreloader does NOT pick it up (it only watches `.py`/`.html`/`.js`).
PostgreSQL is the canonical local database. `run-local.sh` honors the existing
`.env` and automatically runs `docker compose up -d --wait db` before
migrations when `DATABASE_URL` uses a PostgreSQL URL. SQLite remains available
only as an explicit isolated-test or fallback override. The script uses port
8000 by default, detects an occupied port before doing the setup work, and
accepts `PORT=8001 ./run-local.sh` when another process already owns 8000.
Use `./stop-local.sh` to stop only Django; pass `--db` when PostgreSQL should
also be stopped. The command never removes the PostgreSQL data volume.

Styling is Tailwind CSS (utility classes on `attributes.class`, see
`apps/ai_assistant/tailwind_classes.py`) — `pnpm run build:css` must be rerun
after changing the class allowlist there, since it regenerates the safelist
that drives the Tailwind CLI build. Needs Node 20+ (Tailwind v4).
Cross-page UI tokens live in `static/shared/tokens.css`; link that stylesheet
from new server-rendered pages and consume its canonical variables instead of
adding another page-level `:root` palette. Page-specific layout rules may stay
local.
Template palette behavior is separate from cross-page UI tokens: the active
template colors live in `styles.variables`, optional provenance lives in
`styles.palette`, and the server catalog/validation in
`apps/editor/palettes.py` is the source of truth. Reusable `UserPalette` rows
are owner-scoped and expose only validated four-role values through
`/api/user-palettes/`; applying one copies those values into the template
state. Read
`openspec/specs/editor/palettes.md` before changing this contract.
The editor AI and wizard load `static/shared/ai-stream.js` before their
surface scripts; do not reintroduce a second SSE parser or reasoning bubble.
`static/editor/tailwind.css` and `.tailwind-safelist.txt` are gitignored
build artifacts, never commit them.

## Before calling anything "done"

All of these must pass:

```bash
uv run ruff check .
uv run ruff format --check .
AI_PROVIDER=fake uv run pytest            # deterministic AI-backed test gate
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
pnpm test
```

For UI/frontend changes, actually run the feature in a browser (or via a
direct API call with a real session — see below) before reporting success.
Passing tests verifies correctness of the code, not of the feature.

### Browser (Playwright) tests

`tests/e2e/` holds real-browser Playwright specs (`pnpm run test:e2e`) against
a running dev server (`BASE_URL`, default `http://127.0.0.1:8000`) and an
existing test user (`E2E_USERNAME`/`E2E_PASSWORD`). If the host is missing
Chromium's system libs (`libnspr4` etc.) and there's no passwordless sudo to
`playwright install-deps`, run it in the official image instead, from repo
root, with the dev server already running on the host:

```bash
docker run --rm --network host -v "$PWD":/work -w /work \
  mcr.microsoft.com/playwright:v1.61.1-jammy corepack pnpm exec playwright test tests/e2e
```

If the container created a `test-results/` directory owned by its service
user, add `--output /tmp/maqueta-e2e-container` so the reporter does not need
to rewrite mounted container-owned artifacts.

Keep the image tag matched to the installed `@playwright/test` version
(`pnpm exec playwright --version`) — a mismatch fails the browser launch.

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
  never a price/currency from the request, regardless of which of the 8
  gateways (Stripe/Mercado Pago/PayPal/Braintree/Wompi/PayU/ePayco/Bold) is
  used. An `Order` is created by that gateway's signature-verified webhook
  for real payments; the fake-provider dev/test path and the zero-gateway
  free-delivery path are deliberate, narrow exceptions — see
  `openspec/project.md`'s gotchas and `openspec/specs/storefront/spec.md`
  before changing any of these paths.
- **Payment gateway credentials are per-seller, not global.** Configured at
  `/config/` (`PaymentGatewayConfig`, encrypted at rest via
  `apps/storefront/crypto.py`) — never add a project-wide `PAYMENT_PROVIDER`
  setting back; that pattern was deliberately replaced this session because
  this is a multi-tenant editor (each seller has their own gateway
  accounts, same as `/productos/` is already owner-scoped).
- **Anonymous analytics is opt-in and pseudonymous.** Public `/t/<slug>/`
  pages track only after consent, using a separate HttpOnly visitor cookie and
  bounded page/click/mouse events. Never add auth identifiers, IP addresses,
  raw form values, href/query strings, or unvalidated coordinates; use the
  owner-scoped `/analytics/` dashboard and `purge_analytics` retention command.

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
- `UXUI.md` — dated frontend audit, browser evidence, completed UX/accessibility
  acceptance matrix, and continuous-improvement criteria for future UI work.
- `BACKLOG.csv` — known limitations and pending work, structured for
  filtering (status/area/category/verification/blocked_by).
- `learnings.jsonl` — verified technical learnings from past debugging, one
  JSON object per line — check before starting, append after solving (see
  "Using learnings.jsonl" above).
- `openspec/specs/` / `openspec/changes/` — capability specs and in-flight
  change proposals.
- `openspec/specs/editor/palettes.md` — active template palette contract,
  reusable catalog, and verification evidence.
- `TODO.md` — concise status index only; completed implementation checklists
  belong in OpenSpec and the delivery records above.
