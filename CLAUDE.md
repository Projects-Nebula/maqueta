# CLAUDE.md — maqueta (Visual AI Editor)

Project instructions, loaded every session. For stack/layout/commands see
`openspec/project.md`. For tool-agnostic setup/conventions shared with other
coding agents, see `AGENTS.md` — this file only adds Claude Code's subagent
delegation policy on top of it.

## Delegation & context optimization (default policy)

Optimize the main thread's context. The orchestrator (this thread) coordinates;
**push delegable work to sub-agents on lighter models**, and reserve the strong
model (Opus) for what genuinely needs it.

**Delegate to a sub-agent when the work is delegable AND the sub-agent has, or
can be given, enough context to do it without re-deriving the whole project:**

| Work | Agent | Model |
| --- | --- | --- |
| Locate code / "where is X" / list uses | `cavecrew-investigator` or `Explore` | haiku |
| Bounded 1-2 file mechanical edit | `cavecrew-builder` | haiku |
| Broad multi-file exploration / mapping | `Explore` | haiku / sonnet |
| Write a feature across files / moderate reasoning | `general-purpose` | sonnet |
| Run tests / builds / lint and report | `general-purpose` | haiku |
| Diff / branch review | `cavecrew-reviewer` | sonnet |
| Architecture & design decisions | inline (orchestrator) | opus |
| Security-critical logic (`sanitize.py`, `operations.py`, auth) | inline | opus |
| Tricky multi-file integration, final risk review | inline | opus |

**Keep inline (do NOT spawn an agent):**
- Trivial state checks (`git status`, reading 1-3 files to decide).
- One-line / already-understood mechanical edits.
- Work that depends heavily on live conversation context a cold agent would
  have to re-read — delegating there costs MORE tokens, not fewer. Writing docs
  from context already in the thread is usually cheaper inline.

**Rules of thumb**
- Default: code edits run on **sonnet** (delegate a writer). Use Opus only when
  it is 100% necessary — architecture/design decisions, security-critical logic
  (`sanitize.py`, `operations.py`, auth), or tricky multi-file integration where
  a weaker model would plausibly get it wrong. If unsure, it is not necessary →
  sonnet.
- Pass the model explicitly (`model: haiku|sonnet`) — do not let sub-agents
  inherit Opus by default.
- A cold sub-agent starts with no session context. If the task needs prior
  decisions, put them in the sub-agent prompt or point it at `openspec/` files.
- Prefer one well-scoped exploration sub-agent over reading 4+ files inline.
- Single writer thread for implementation; no parallel writers unless isolated
  worktrees are explicitly approved.

**Investigation trip-wire (this is the REPEATED failure — enforce at the moment,
not as vague advice):**
- The "delegate exploration" rule counts *lookups*, not distinct files. Reading
  the SAME big file (e.g. `editor-core.js`) 4+ times, or running 4+
  greps/Reads to locate-and-understand code, IS an investigation → delegate it.
  A "read function A → read function B it calls → read C" chain counts; batch it
  into ONE `cavecrew-investigator` call that returns those functions verbatim.
- **Debugging is NOT an exemption.** Split it in two: the *location/mapping* pass
  ("where are these functions, what does each do, what calls what") is delegable
  → one investigator call. Only the *diagnosis* — forming and discarding
  hypotheses across the returned code — stays inline on Opus. Do the delegated
  mapping FIRST, then reason over its result. Do not rationalize sequential
  inline code-tracing as "diagnosis".
- Before the FIRST locate-Read/grep, ask: "am I locating/understanding code, or
  deciding from something I already have in the thread?" Locating → delegate.
  Never open a 4th file — or re-open one file a 4th time — inline to understand
  it. When in doubt, one investigator call is cheaper than five inline reads.

## Before "done"

All quality gates in `openspec/project.md` must pass: ruff check, ruff format
--check, pytest, `manage.py check`, `makemigrations --check`, and the Node test.

## Conventions

- Python + deps via `uv` only (never pip/poetry/pipenv).
- Code/comments/identifiers in English; user-facing app strings in Spanish.
- Security is server-side and model-independent; never trust frontend/model
  input. `OPENAI_API_KEY` never reaches the browser.
- Do not "clean up" `static/editor/editor-core.js` — it is the original editor
  IIFE verbatim plus a facade; see `openspec/project.md` gotchas.
