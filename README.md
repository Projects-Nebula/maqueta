# Visual AI Editor

Django backend + AI assistant wrapped around an existing visual HTML/JSON page
editor. The editor keeps all of its manual features; the AI adds a panel that
turns a natural-language instruction into **validated, structured operations**
you preview and apply as a single undo step. A second AI-guided flow, the
**template wizard** (`/wizard/`), builds a whole page from scratch through a
chat + dynamic question form instead of starting from a curated template. The
editor is served behind login and same-origin, so the browser's **session
cookie (with CSRF)** authenticates the API — no API key ever reaches the
browser, no token/device flow needed.

## Architecture

```
config/            Django project (settings split: base/development/production)
apps/
  accounts/        Login/logout (Django auth views)
  editor/          /editor/, /home/, /gallery/, /wizard/; Template · UserTemplate ·
                    UserTemplateRevision models + owner-scoped DRF API
  ai_assistant/    Edit-time transform endpoint + the template wizard's 3
                    endpoints; sanitizer, document validator, providers, prompts
  projects/        Project + ProjectRevision API (owner-scoped, no IDOR)
templates/         login, editor shell, home/gallery pickers, wizard page
static/editor/     editor.css, editor-core.js (verbatim editor), editor-ai.js,
                    template-wizard.js, wizard.css
tests/             pytest suite + a Node test for applyAIOperations
```

Request flow for an AI edit:

1. User logs in; the editor page (`ensure_csrf_cookie`) leaves a `csrftoken`
   cookie in the browser.
2. Editor sends **only** the selected node + nearby context + design variables
   + the real current body structure (`body_outline`) + the instruction to
   `POST /api/ai/editor/transform/` with the session cookie and an
   `X-CSRFToken` header.
3. A conversational model first rewrites a vague instruction ("hazlo mas
   grande") into an explicit one using that context; the main model then
   generates operations from it. Both stream their reasoning back over
   Server-Sent Events as they think, then a validated terminal result — the
   backend **validates every operation** before it can reach the browser.
4. `applyAIOperations` applies the vetted operations to a clone, previews it,
   and — on Apply — commits it as one history snapshot.

Request flow for the template wizard (`/wizard/`):

1. A chat asks what page the user wants; their free-text reply goes to
   `POST /api/ai/wizard/questions/`, which streams back an AI-tailored
   question form (id/label/type/options — text, textarea, or select only).
2. The filled form goes to `POST /api/ai/wizard/review/`, which decides
   `ready` or asks one clarifying question via chat (looped, capped at 5
   rounds).
3. Once ready, `POST /api/ai/wizard/generate/` produces the page in two AI
   calls — structure (the HTML tree, styled inline with Tailwind utility
   classes) first, then just the brand-color palette (`styles.variables`) —
   reducing how often a single huge generation gets cut off mid-response.
   The assembled document is validated whole (`document_validation.py`)
   before it's ever returned.
4. The client saves the result through the **already-existing**
   `POST /api/user-templates/` endpoint — the wizard has no persistence of
   its own, it just produces a document the normal save flow already knows
   how to store.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node 20+ (Tailwind CSS build — `npm install && npm run build:css`)
- Docker + Docker Compose (optional, for the reproducible stack)

## Local setup

```bash
uv sync                                   # create .venv + install (from uv.lock)
cp .env.example .env                      # then edit as needed
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver         # http://localhost:8000/editor/
```

`AI_PROVIDER=fake` (the default when `OPENAI_API_KEY` is empty) lets the whole
flow work offline — the fake provider returns safe example operations.

## Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
node tests/js/apply.test.js               # frontend applyAIOperations tests
```

## Docker

```bash
cp .env.example .env                      # set DJANGO_SECRET_KEY, etc.
docker compose up --build
# App on http://localhost:8000 (Postgres + Gunicorn, migrations run on start)
```

The image is multi-stage, installs with `uv sync --frozen --no-dev`, collects
static files, runs as a non-root user, and exposes a `/healthz/` healthcheck.

## Configuring the AI provider

The provider is swappable via the `AIProvider` interface
(`apps/ai_assistant/providers.py`); tests use `FakeAIProvider`. Two real
providers are available:

```env
# OpenAI (Responses API)
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini      # or any Responses-API model; never hardcoded in code

# OpenCode Zen (OpenAI-compatible AND Anthropic-Messages-compatible gateway)
AI_PROVIDER=opencode_zen
OPENCODE_ZEN_API_KEY=sk-...
OPENCODE_ZEN_MODEL=mimo-v2.5-pro        # heavy structured generation
OPENCODE_ZEN_CHAT_MODEL=mimo-v2.5       # conversational calls (chat-shaped)
AI_MAX_OUTPUT_TOKENS=32000              # long generations need real headroom
```

**Two roles, two models.** A conversational model (`OPENCODE_ZEN_CHAT_MODEL`)
handles chat-shaped calls — the editor's instruction-clarification pass and
the wizard's question/review steps — while the main model
(`OPENCODE_ZEN_MODEL`) handles the one heavy call per flow: generating
structured operations or the full page document, where JSON reliability
matters more than conversational tone.

**Model routing matters on OpenCode Zen.** Some models (MiniMax, the Qwen3.7
family) are served over the Anthropic Messages API (`/v1/messages`) rather
than OpenAI chat/completions — calling the wrong shape doesn't error, it
produces intermittent malformed JSON on long generations. `build_provider()`
routes automatically by model name (`OPENCODE_ZEN_ANTHROPIC_MODELS` in
`providers.py`); check OpenCode Zen's own model table before adding a new one
to `OPENCODE_ZEN_MODEL`/`OPENCODE_ZEN_CHAT_MODEL`.

## Using the assistant in the editor

1. Open `/editor/` (log in first).
2. Go to the **Asistente IA** tab.
3. Click an element in the preview to select it.
4. Type an instruction (e.g. "Haz este título más comercial") → **Generar cambios**.
5. Review the summary + operations, then **Aplicar cambios** (one undo step) or
   **Descartar**. `Ctrl/Cmd + Z` undoes an applied AI change.

The AI panel calls the API with the browser session + CSRF token, so being
logged in is all that is needed — no key or connection step.

## Using the template wizard

1. From `/home/`, click **✦ Crear mi propio template con IA** (or go to
   `/wizard/` directly).
2. Answer the opening chat question describing the page you want.
3. Fill the form the AI generates for you, tailored to that description.
4. If the AI needs one more detail it asks via chat; otherwise it goes
   straight to generating the page (watch the reasoning stream live).
5. Name the result (AI-suggested, editable) and **Guardar en mi galería** —
   it appears in `/gallery/` like any other saved template.

You can also attach images (step 3 or 4) — they're resized/re-encoded
server-side and made available for the AI to place in the generated page
(`state.assets`, never AI-authored directly — see `BACKLOG.csv`).

## Security notes

- Auth is the Django session (same-origin) + CSRF; the AI endpoint requires an
  authenticated session and rejects requests without a valid `X-CSRFToken`.
- The AI can never emit scripts, `on*` handlers, `iframe/object/embed`,
  `javascript:`/`data:text/html` URLs, or a non-allowlisted Tailwind class
  (`apps/ai_assistant/tailwind_classes.py`) — enforced server-side in
  `sanitize.py` + `operations.py` (incremental edits) and
  `document_validation.py` (whole documents from the wizard), independent
  of the model. A malformed AI response may get a best-effort JSON-syntax
  repair (`json-repair`), but the repaired result still goes through the
  same full validation before it's ever returned — a "fixed" but unsafe or
  structurally broken document is still rejected.
- Endpoints are throttled per scope (`ai_transform`, `ai_wizard_questions`,
  `ai_wizard_review`, `ai_wizard_generate`); project/template access is
  owner-scoped (no IDOR); provider keys stay server-side, never in the
  browser.
