# Project — Visual AI Editor

> Session bootstrap. Read this first when picking the project up in a new
> session. It captures what the project is, how it is laid out, how to run it,
> and the conventions that are NOT obvious from the code.

## What it is

Django backend + AI assistant wrapped around an existing visual HTML/JSON page
editor. Users pick a starting **template** (a curated base one from `/home/`, or
one of their own saved ones from `/gallery/`) — or build one from scratch via
the **AI wizard** at `/wizard/` — select an element in a live preview, describe
a change in natural language, and the backend returns **validated structured
operations** they preview and apply as a single undo step. The editor is
served behind login and same-origin, so the browser's **session cookie (with
CSRF)** authenticates API calls — no API key ever reaches the browser, and no
token/device flow is needed.

## Stack

- Python 3.12, managed exclusively with `uv` (never pip/poetry/pipenv).
- Django 5.2, Django REST Framework.
- django-environ, django-cors-headers, whitenoise, gunicorn.
- AI providers: `OpenAIProvider` (OpenAI SDK, Responses API),
  `OpenCodeZenProvider` (OpenAI SDK, OpenAI-compatible chat/completions),
  `AnthropicMessagesProvider` (`anthropic` SDK, for OpenCode Zen models
  routed via `/v1/messages` — see gotchas), and `FakeAIProvider` (offline,
  what tests use). `build_provider()` picks per-call by model name.
  `json-repair` salvages malformed AI JSON before falling back to an error.
  `jsonschema` for the operation schema.
- **PostgreSQL for local dev and production** (via `DATABASE_URL`; the repo
  `compose.yaml` provides a `db` service). SQLite only as the fallback default
  when `DATABASE_URL` is unset.
- pytest + pytest-django + pytest-mock, ruff (lint + format).
- Docker + Docker Compose.

## Layout

```
config/            settings base/development/production, urls, CSP middleware, wsgi/asgi
apps/accounts      login/logout
apps/editor        serves /editor/ /home/ /gallery/ /wizard/; Template ·
                   UserTemplate · UserTemplateRevision models, admin,
                   UserTemplate DRF API (api_urls, revisions
                   history/restore/delete); ensure_csrf_cookie
apps/ai_assistant  sanitize · operations · providers (Anthropic/OpenAI-compatible/
                   fake, model-based routing) · schema · prompts · service
                   (EditorAIService: chat model clarifies instruction → main
                   model generates operations) · serializers · views (edit-time
                   transform) · wizard_service (WizardAIService: same two-role
                   split; generate is itself 2 calls — structure then styles)
                   · wizard_views · document_validation (sanitizes a FULL
                   generated document, strict key checks at every level) · sse
apps/projects      Project + ProjectRevision API (owner-scoped)
templates/         registration/login · editor/editor.html · editor/home.html ·
                   editor/gallery.html · editor/template_wizard.html
static/editor/     editor.css · editor-core.js · editor-ai.js · seed-loader.js ·
                   save-template.js · wizard.css · template-wizard.js
tests/             pytest + tests/js/apply.test.js (Node)
openspec/          this spec set (project.md · specs/ · changes/)
```

## Templates

- `Template` (base catalog, global, `slug`) shown on `/home/`; `UserTemplate`
  (per-user, owner FK) shown on `/gallery/`. Both hold the full editor `state`
  as JSON (`Template.state` may be null → built-in default page).
- `editor_view` reads `?t=<slug>` (base) or `?ut=<id>` (user, owner-scoped)
  and injects the state server-side via `{{ ...|json_script:"template-seed" }}`;
  `seed-loader.js` applies it with `EditorCore.commitProposal`. Both gallery
  pages render cards server-side (no client fetch).
- "☆ Guardar" saves the current state as a `UserTemplate` via the owner-scoped
  `UserTemplateViewSet` (POST create / PATCH update, no IDOR). Base templates are
  seeded by data migration `apps/editor/migrations/0002_seed_templates.py`.
- Updating a `UserTemplate` auto-snapshots the previous state into a
  `UserTemplateRevision` (only on real change); the save modal's "Historial"
  lists them with restore/delete via `…/user-templates/<id>/revisions/`.
- There is no "blank" base `Template` anymore (removed by data migration
  `apps/editor/migrations/0005_remove_blank_template.py`) — its role is now
  the **wizard** (`/wizard/`, `apps/editor/views.py::template_wizard_view`):
  a chat asks what page the user wants, the AI generates a tailored question
  form (`POST /api/ai/wizard/questions/`), a review step decides if it's
  ready or needs one clarification via chat (`POST /api/ai/wizard/review/`,
  looped up to 5 rounds — `MAX_REVIEW_ROUNDS` in `template-wizard.js`), then
  `POST /api/ai/wizard/generate/` produces the document in **two** AI calls
  (`WizardAIService.stream_generate_document`): structure (HTML tree, no
  styles) first, then styles (CSS for the classes that structure
  introduced, given the body as context) — a single call asking for both
  was where the model most reliably ran out of steam and silently dropped
  the trailing keys. `components`/`assets` (always `{}`, no image-upload
  feature exists yet) are force-injected in Python rather than trusted from
  the model — it reliably omitted them too, even in the shorter call.
  The assembled document is validated whole by
  `document_validation.sanitize_document` (distinct from
  `operations.validate_operations`, which only validates incremental edits
  against an existing page). None of the three wizard endpoints persist
  anything — the client saves the result via the same
  `POST /api/user-templates/` the editor's "☆ Guardar" already uses.
  All three are SSE (same `event: reasoning` → `event: done`/`error` contract
  as `/api/ai/editor/transform/`, see `apps/ai_assistant/sse.py`).
- The in-editor assistant (`EditorAIService.stream_generate_operations`) has
  the same two-role split: a chat model rewrites the user's raw instruction
  ("hazlo mas grande") into an explicit one using page context
  (`_clarify_instruction`, falls back to the raw instruction on any
  provider error — it's an enhancement, not a hard requirement) before the
  main model generates operations from it.

## Commands

```bash
uv sync
docker compose up -d db                     # local PostgreSQL (creds editor/editor/editor)
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver          # http://localhost:8000/home/
# Quality gates (all must pass before "done"):
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
node tests/js/apply.test.js
# Docker:
docker compose up --build
```

## Conventions

- **Delegation & context optimization:** see `CLAUDE.md` (auto-loaded). Push
  delegable work to sub-agents on lighter models (haiku/sonnet); keep only
  architecture, security-critical logic, and tricky integration inline on Opus.
- **Dependencies + Python via `uv` only.** No pip/poetry/pipenv.
- **Code, comments, UI copy, identifiers default to English.** User-facing app
  strings (login, activate, editor panel) are Spanish to match the editor.
- **Security is server-side and model-independent.** `sanitize.py` +
  `operations.py` are the single source of truth for what a node tree / AI
  operation may contain. Never trust paths, nodes, or operations from the
  browser or the model.
- **AI never returns free HTML** — only the validated operation protocol.
- **Never expose `OPENAI_API_KEY` to the frontend.** Never send the full JSON
  document to the AI; send only the selected node + nearby context + design
  variables + instruction.
- **One AI apply = one undo step** (`EditorCore.commitProposal`).
- Migrations excluded from ruff.

## Non-obvious gotchas

- **CSP blocks inline scripts.** `config/middleware.py` sets
  `script-src 'self'` (no `'unsafe-inline'`), so any inline `<script>…</script>`
  with executable JS is SILENTLY blocked by the browser — no console error
  unless you look. ALL page logic MUST live in an external `static/editor/*.js`
  file (`script-src 'self'`). Inline `type="application/json"` data (e.g.
  `json_script`) and inline styles (`style-src 'unsafe-inline'`) are fine; same
  origin fetch is fine (`connect-src 'self'`).
- `static/editor/editor-core.js` is the original `editor.html` IIFE verbatim
  with a `window.EditorCore` facade injected **inside** the IIFE (top-level
  `let state`/`selectedPath` are not on `window`). Do not "clean it up" — it is
  intentionally near-byte-identical. To integrate with the core (e.g.
  `commitProposal`, `clearSelection`), ADD a method to the facade object at the
  end; the surrounding editor-ai.js drives it. Never patch the IIFE body.
- Dev overrides static storage to plain `StaticFilesStorage` so pages render
  without `collectstatic`; production uses the manifest storage. After deleting
  a `.py` module, `rm` its stale `__pycache__/*.pyc` or the dev reloader
  keeps importing it → crash loop.
- Production exempts `/healthz/` from SSL redirect for the container healthcheck.
- The AI panel polls selection every 400ms (`editor-ai.js`) instead of patching
  the core; the same poll positions the floating action bar and binds the
  click-outside-to-deselect handler.
- `AI_MAX_OPERATIONS` (default 150) caps ops per AI response. Each CSS property is
  its own `set_css_declaration` op, so generating a styled section is op-heavy —
  keep the cap generous or the model's valid output gets rejected as
  "too many operations".
- `AI_PROVIDER` selects the provider; `fake` (default when no key) makes the
  whole flow work offline and is what tests rely on.
- `AI_MAX_OUTPUT_TOKENS` (default 32000) caps model output tokens. Without it
  set explicitly (or set too low), a full-page wizard generation (lots of
  styles.rules JSON) can get cut off mid-response by the provider's own
  default cap, producing invalid/truncated JSON (`AIResponseFormatError`) —
  this is NOT a prompt or validation bug, it's starving the model of output
  budget.
- MiniMax (via `opencode_zen`) rejects JSON Schema **type unions**
  (`"type": ["string", "null"]`) in `response_format.json_schema` with a
  400 *before generation even starts* — use a single type (e.g. plain
  `"string"`) and handle the null/empty case in Python instead
  (`wizard_service.py`'s `stream_review_answers` already does this for
  `clarification`). Not obvious from the error, which just says "mismatched
  type with value" at a byte offset into the schema.
- **Some OpenCode Zen models need `/v1/messages`, not `/v1/chat/completions`.**
  Per OpenCode Zen's own model table: Grok/GLM/Kimi/DeepSeek/MiMo are
  OpenAI-compatible; MiniMax and the Qwen3.7 family are Anthropic-Messages-
  compatible. Calling the wrong shape does NOT error cleanly — it produces
  intermittent malformed JSON on long generations, which looks exactly like
  "the model is unreliable" until you check which endpoint it actually
  wants. `providers.OPENCODE_ZEN_ANTHROPIC_MODELS` is the routing table;
  `build_provider()` picks `AnthropicMessagesProvider` vs
  `OpenCodeZenProvider` by model name. Before adding a new model to
  `OPENCODE_ZEN_MODEL`/`OPENCODE_ZEN_CHAT_MODEL`, check which endpoint it
  needs and update that set if it's Anthropic-Messages-compatible.
- **`deepseek-v4-pro`/`deepseek-v4-flash` are broken on this account**,
  failing identically via both protocols with `"Error from provider
  (Console Go): Upstream request failed"` (400) — confirmed not a protocol
  issue (tested both), it's opencode.ai's own upstream for that model
  family. Don't re-diagnose this from scratch; check with opencode.ai
  support first.
- **`json-repair` can "fix" JSON syntax while corrupting document structure.**
  A dropped comma/bracket near a truncation point can get "repaired" into
  syntactically valid JSON that closes an array early and leaves what
  should have been array items as dangling sibling keys one level up
  instead (a whole section silently missing from `body.children`,
  reappearing as stray `type`/`tag`/`attributes`/`children` keys on
  `document` itself). `document_validation.py` guards against this with
  exact key-set checks (`set(x.keys()) == {...}`) at every nesting level,
  not just presence checks — this is why those checks exist and shouldn't
  be loosened without understanding this failure mode first.
- **`.env` changes need a full server restart, not just a save.** Django's
  `StatReloader` (`runserver`'s autoreload) only watches `.py`/`.html`/`.js`
  — `.env` is read once at process start via `environ.Env.read_env()` in
  `config/settings/base.py`. Changing a model name or API key in `.env` and
  expecting the next request to pick it up silently doesn't work; kill and
  restart `runserver`.
- Rejection reasons for wizard document generation are logged at `INFO`
  (not `DEBUG`) permanently in `wizard_service.py`
  (`"rejected AI-generated document: <reason>"`) — the model's output isn't
  deterministic, so a failure doesn't reliably reproduce on retry; the
  reason needs to already be in `server.log` the first time, not require
  flipping the log level and asking for another attempt.

## Related durable context

- `CHANGELOG.md` — what shipped, by version.
- `BACKLOG.csv` — pending work and known limitations, structured for
  filtering (status/area/category/verification/blocked_by).
- `openspec/specs/` — current capability specs (source of truth for behavior).
- `openspec/changes/` — in-flight change proposals (delta specs).
- Session memory: `~/.claude/projects/-home-sebitcode-projects-maqueta/memory/`.
