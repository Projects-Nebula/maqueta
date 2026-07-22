# REFACTOR.md — Migrate styling to Tailwind CSS

**Audience**: an agent executing this refactor end to end, autonomously,
without stopping for clarification. Every decision that would normally be
"ask the user" has already been made below — follow it as written. If you
hit a fact about the codebase that contradicts something stated here,
trust the code and adapt, but do not silently change the target
architecture (Section 1) without flagging it loudly in your final report.

**Definition of done**: every phase in Section 4 checked off, every test in
Section 9 passing, the manual verification checklist in Section 10 run for
real (browser, not just unit tests), `BACKLOG.md` and `AGENTS.md` updated,
one commit per phase (see `work-unit-commits` convention already used in
this repo's git history — `git log --oneline` shows the pattern: one
focused commit per feature, Conventional Commits, no
`Co-Authored-By`/AI-attribution trailers).

---

## 0. Why this refactor

Today, page styling is a custom JSON DSL (`state.styles.rules`): the AI (or
a human) writes `{selector, declarations}` objects, validated property-by-
property against `CSS_PROPERTY_ALLOWLIST` in `apps/ai_assistant/sanitize.py`,
then compiled into a `<style>` tag client-side by
`static/editor/editor-core.js`'s `buildCss()`.

Two concrete pains this refactor solves:

1. **Wizard generation reliability** (see `BACKLOG.md`'s "Pending" section,
   item 1). Full-document generation asks the model to emit complete
   `{selector, declarations}` objects for every class it invents — verbose,
   token-heavy, and the model periodically drops content generating it under
   load. Tailwind utility classes are short, finite, known strings — much
   less output per element, much lower truncation risk.
2. **Ongoing allowlist maintenance** (see `BACKLOG.md` — "Expand the CSS
   property allowlist" is explicitly open-ended/never-done). A structured,
   finite Tailwind-class allowlist (Section 3) is more bounded than an
   open-ended CSS property/value combinatorial space.

Trade-off accepted going in: this touches the AI prompts, the validation
layer, the per-element style editor UI, the rendering pipeline, and adds a
real JS build step to a project that has deliberately avoided one so far.
That cost is accepted — do not re-litigate it mid-execution.

---

## 1. Non-negotiable architecture decisions

Read this section fully before writing any code. These are the load-bearing
choices; do not deviate.

### 1.1 Tailwind v4, CLI-only, no Node runtime in production

Use `@tailwindcss/cli` (Tailwind v4's standalone CLI). Do **not** use the
Tailwind Play CDN script (`<script src="https://cdn.tailwindcss.com">`) —
it JIT-compiles client-side via inline `<script>`, which violates this
project's CSP (`script-src 'self'`, see `apps/ai_assistant/sanitize.py`'s
comments and `config/settings/base.py`'s CSP config) and is explicitly
"not for production use" per Tailwind's own docs.

The CLI runs **only at build time** (local dev, CI, and the Docker image
build stage). The runtime container never runs Node — it serves a
pre-compiled static CSS file via WhiteNoise, exactly like every other
static asset today.

### 1.2 The problem: dynamic class names defeat static content scanning

Tailwind's CLI generates CSS only for class names it can find by scanning
files matching a `content`/`@source` glob at build time. Here, class names
are **chosen by an LLM at request time and stored in Postgres JSON
(`state.document.body...attributes.class`)** — they never appear in any
file on disk. A naive Tailwind setup would compile **zero** utilities for
AI-generated content.

**Solution: safelist-via-sentinel-file, driven by the same allowlist that
already gates security.** Concretely:

1. Define the finite set of allowed Tailwind utility classes in Python
   (Section 3) — this is the *single source of truth*, used both to
   validate AI/editor output (already the existing security model:
   compare to today's `CSS_PROPERTY_ALLOWLIST`) and to tell Tailwind what
   to compile.
2. A management command (Section 4, Phase 1) expands that allowlist into
   every literal class string and writes them, one per line, into a
   plain-text file Tailwind's CLI treats as a content source (e.g.
   `static/editor/.tailwind-safelist.txt`). Tailwind's scanner "sees" every
   allowed class in that file and compiles CSS for all of them,
   unconditionally — regardless of whether they appear in any real page.
3. Result: the compiled CSS always contains **exactly and only** classes
   the system is allowed to emit. No content-scanning gap, no drift between
   "what's allowed" and "what's compiled" — they're generated from the same
   list, in the same build step.

This approach is Tailwind-version-agnostic (works whether v4's `@source`
directive or v3's `content` array) and needs no framework-specific
"safelist" config API — it degrades gracefully.

### 1.3 `styles.variables` (CSS custom properties) survives unchanged

The global design-tokens panel ("Diseño global" in `#sectionModal`,
`templates/editor/editor.html:115-146`) already writes brand colors,
font-family, max-width, border-radius, section-spacing into
`state.styles.variables` (`--color-primary`, etc.), validated by
`check_css_variable` in `sanitize.py`, injected as a `:root { ... }` block
by `buildCss()`. **Do not touch this mechanism.** Tailwind utilities can
reference these directly via arbitrary-value syntax:
`bg-[var(--color-primary)]`, `text-[var(--color-text)]`. This is the bridge
between per-project brand theming (which must stay dynamic, per-document)
and Tailwind's utility classes (which are static/finite).

Only arbitrary values of the exact shape `var(--allowed-variable-name)`
are permitted through validation (Section 3.3) — never raw arbitrary values
like `bg-[#ff0000]` or `w-[999999px]` or anything containing `url(`,
`expression(`, `javascript:`, etc. Reuse `CSS_VALUE_FORBIDDEN` and
`check_css_variable`'s existing name-format checks as the base.

### 1.4 `styles.rules` / `styles.mediaQueries` / `styles.keyframes` are frozen, not deleted

These fields **stay in the JSON schema** for backward compatibility with
every `Template`/`UserTemplate`/`Project` row already in Postgres. Existing
saved pages must keep rendering exactly as they do today.

- `apps/editor/rendering.py`'s `_render_styles`/`_render_rule_list` and
  `editor-core.js`'s `buildCss()` **keep rendering `styles.rules` /
  `mediaQueries` exactly as they do now** — this is the legacy rendering
  path, permanent, not removed.
- Going forward, **new** AI-generated content (wizard full-document
  generation, and the editor's AI-transform panel) **stops writing to
  `styles.rules`/`mediaQueries`** — mirrors exactly how `components`/
  `assets` were historically forced to `{}` in `wizard_service.py`, then
  later `assets` was un-frozen for the image-upload feature (see git log:
  `9af3aab`, `ac75c39`). Same pattern, same file.
- **No automatic conversion migration** of old `styles.rules` into
  Tailwind classes. That is explicitly out of scope (Section 8) — it is a
  lossy, error-prone, high-effort translation problem on its own and is
  not required for this refactor to deliver value. A user can still open
  an old template and manually re-style elements with the new class-based
  panel; existing content just isn't auto-upgraded.
- `styles.mediaQueries` (the `@media` feature shipped in commit `9af3aab`)
  becomes **functionally superseded** by Tailwind's responsive variant
  prefixes (`sm:`, `md:`, `lg:`, ...) for anything newly authored. Leave the
  feature and its validation in place (legacy content depends on it); stop
  advertising it in prompts going forward.

### 1.5 No new AI operation types — reuse `set_attribute`

`apps/ai_assistant/operations.py`'s `set_attribute` action already handles
`class` generically (list or string, see `_validate_class_or_text`). **Do
not invent `add_class`/`remove_class`/`set_classes` operation types.** The
AI (and the editor's manual UI) express all class changes as
`set_attribute` with `attribute: "class"`, list-of-strings value, validated
against the new Tailwind class allowlist. This is a deliberate
simplification — it keeps the operations surface small and reuses
existing, already-tested code paths (`editor-ai.js`'s `case "set_attribute"`
handler at line 85, and the equivalent in the op-summary label generator
around line 370).

`set_css_declaration` / `remove_css_declaration` / `set_style_variable`
**operation types stay valid** (for editing old documents that still carry
`styles.rules`) but the AI system prompts stop telling the model to use
`set_css_declaration`/`remove_css_declaration` for new styling (Section
4, Phase 3). `set_style_variable` keeps being advertised — it still
targets `styles.variables`, unaffected by this refactor (see 1.3).

### 1.6 The per-element "Estilo rápido" quick-style panel currently bypasses everything

**Read this carefully — it is not obvious from the outside.** The
per-element inspector's "Estilo rápido del elemento" quick-fields
(`editor-core.js`, `renderInspector()`, around line 2464 —
`nodeBackground`/`nodeColor`/`nodePadding`/`nodeMargin`/`nodeWidth`/
`nodeTextAlign`) do **not** go through `styles.rules` at all. They call
`setInlineStyleProperty(node, property, value)` (line 2373), which writes
a literal inline `style="..."` attribute directly onto the node
(`node.attributes.style`). This is a **second, parallel styling mechanism**
that exists today purely for manual (non-AI) edits.

Why this was previously safe: `UserTemplateSerializer`
(`apps/editor/serializers.py`) has **no validation on `state`'s shape at
all** — a manual save never goes through `sanitize_node`/`check_attributes`
(those only run for AI-authored content, in `operations.py` and
`document_validation.py`). The AI is separately hard-blocked from ever
emitting a `style` attribute (`check_attributes`: `"inline style attribute
not allowed"`; `operations.py`'s `set_attribute` case: `"style attribute
not allowed"`).

**This refactor migrates this panel too**, so there is one consistent
styling mechanism (Tailwind classes) instead of three coexisting ones
(legacy `styles.rules`, legacy inline `style`, new Tailwind classes) after
the change. See Phase 5. The inline-`style`-on-node mechanism does not need
a security fix (it was never AI-reachable and manual edits are
self-trusted, same as any other field the owner edits) — it needs
replacing so authoring is consistent, not because it was unsafe.

### 1.7 Compiled CSS is a build artifact — gitignored, built fresh every time

Do not commit the compiled Tailwind CSS output. Add it to `.gitignore`
alongside `staticfiles/` (already gitignored). It gets generated by:

- `run-local.sh` (add the build step before `runserver`)
- `.github/workflows/ci.yml` (new step)
- `Dockerfile` (new stage/step, before `collectstatic`)

---

## 2. Files you will touch — read each before editing

| File | Role today | What changes |
|---|---|---|
| `apps/ai_assistant/sanitize.py` | `CSS_PROPERTY_ALLOWLIST`, `check_css_declaration`, `check_css_selector`, `check_css_variable`, `check_css_media_query`, `check_asset_entry`, `check_attributes`, `URL_ATTRS`, `sanitize_node` | Add the Tailwind class allowlist/validator (Section 3). Existing functions stay for legacy-document validation. |
| `apps/ai_assistant/operations.py` | `ALLOWED_ACTIONS`, `_validate_class_or_text`, `_validate_one` | `_validate_class_or_text`'s `class` branch calls the new Tailwind class validator. No new action types. |
| `apps/ai_assistant/document_validation.py` | `_check_styles`, `_check_rule_list`, `_validate` | New documents: validate that body-tree node `class` attributes use only allowlisted Tailwind classes (reuse `sanitize_node`'s existing attribute walk — extend `check_attributes` or add a sibling check invoked from the same place). `styles.rules`/`mediaQueries` keep being validated exactly as today (for any legacy-shaped content that flows through here) — the wizard just won't populate them anymore (Phase 4). |
| `apps/ai_assistant/prompts.py` | `SYSTEM_PROMPT` (editor transform), `WIZARD_DOCUMENT_STRUCTURE_PROMPT`, `WIZARD_STYLES_PROMPT` | Rewrite styling instructions to Tailwind classes (Phase 4). |
| `apps/ai_assistant/wizard_service.py` | `stream_generate_document` — two-phase (structure, then styles) generation, forces `components={}`, builds `assets` server-side | Classes are authored inline during the *structure* phase (they're part of node attributes, not a separate stylesheet). Re-evaluate whether the *styles* phase call is still needed at all (Phase 4 — likely yes, but repurposed to only emit `styles.variables`, not `styles.rules`). |
| `apps/editor/rendering.py` | `_render_node`, `_render_attributes`, `_render_styles`, `_render_rule_list`, `thumbnail_srcdoc` | No functional change required — `_render_attributes` already serializes `class` as-is (Tailwind classes render identically to any other class string). Must add a `<link>` to the compiled Tailwind CSS in the thumbnail's `<head>` so previews actually show Tailwind-styled output (Phase 6). |
| `static/editor/editor-core.js` | Huge IIFE — **do not restructure it wholesale** (existing project convention, see `CLAUDE.md`). `buildCss()`, `buildHtmlDocument()`, `renderInspector()`, `setInlineStyleProperty`/`getInlineStyle`, `EditorCore` facade | Surgical, additive changes only: keep `buildCss()`/`buildHtmlDocument()` legacy paths; add the Tailwind `<link>` to `buildHtmlDocument()`'s emitted `<head>`; rework `renderInspector()`'s "Estilo rápido" fields to toggle Tailwind classes instead of calling `setInlineStyleProperty` (Phase 5). |
| `static/editor/editor-ai.js` | Operation-apply switch (`case "set_attribute"` etc., ~line 85), op-summary label generator (~line 370) | Minimal — `set_attribute`/`class` already works. Possibly extend the human-readable op-summary label for class changes to be friendlier (e.g. "cambió el estilo" instead of raw class diff) — optional polish, not required for correctness. |
| `static/editor/template-wizard.js` | Wizard chat flow, image upload (built earlier this session) | No changes expected — it just displays/saves whatever `state` the wizard returns; shape-agnostic. |
| `package.json` | `@playwright/test` devDependency, `test`/`test:e2e` scripts | Add `tailwindcss`/`@tailwindcss/cli` as devDependencies, add a `build:css` script. |
| `Dockerfile` | Multi-stage: `builder` (uv sync), `runtime` (copies app, runs `collectstatic`) | Add Node + the Tailwind build to the `builder` stage (or a new stage), before `collectstatic` copies static files into the image. |
| `.github/workflows/ci.yml` | ruff, pytest (Postgres service), node test, docker build | Add a "build Tailwind CSS" step before pytest (if any test touches rendered CSS) and ensure the Docker build job still passes with the new Dockerfile stage. |
| `run-local.sh` | `uv sync`, `.env` bootstrap, `migrate`, `runserver` | Add `npm install` + the Tailwind build step before `runserver`. |
| `.gitignore` | Already excludes `staticfiles/`, `node_modules/`, `media/`, `.codegraph/` | Add the compiled Tailwind CSS output path and the generated safelist file. |
| Every test file listed in Section 9 | — | Update fixtures/assertions for the new class-based shape. |

---

## 3. The Tailwind class allowlist — concrete design

Put this in a new module, `apps/ai_assistant/tailwind_classes.py`, imported
by `sanitize.py`/`operations.py`/`document_validation.py` (mirrors how
`sanitize.py` itself is a focused, single-purpose module).

### 3.1 Structure: rules, not a giant literal set

Do not hand-enumerate every literal class string (e.g. every `p-0`
through `p-96` × every side × every breakpoint prefix is tens of
thousands of combinations). Define **structured rules**: a set of allowed
utility "families", each as a prefix + an allowed value-scale, expressed
as a compiled regex or a prefix+suffix-set pair. Example shape (adjust
exact scales to match Tailwind v4's default scale — verify against
`@tailwindcss/cli`'s generated output during Phase 1, don't guess):

```python
# apps/ai_assistant/tailwind_classes.py
SPACING_SCALE = {"0", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "5",
                  "6", "7", "8", "9", "10", "11", "12", "14", "16", "20",
                  "24", "28", "32", "36", "40", "44", "48", "52", "56",
                  "60", "64", "72", "80", "96", "px", "auto"}

UTILITY_FAMILIES = {
    # prefix -> allowed value set (or a compiled regex for open-ended scales)
    "p": SPACING_SCALE, "px": SPACING_SCALE, "py": SPACING_SCALE,
    "pt": SPACING_SCALE, "pr": SPACING_SCALE, "pb": SPACING_SCALE, "pl": SPACING_SCALE,
    "m": SPACING_SCALE, "mx": SPACING_SCALE, "my": SPACING_SCALE,
    "mt": SPACING_SCALE, "mr": SPACING_SCALE, "mb": SPACING_SCALE, "ml": SPACING_SCALE,
    "gap": SPACING_SCALE, "gap-x": SPACING_SCALE, "gap-y": SPACING_SCALE,
    # ... sizing (w, h, min-w, max-w, min-h, max-h), typography (text, font,
    # leading, tracking), colors (bg, text, border — Tailwind's default
    # palette names/shades only), borders (rounded, border, border-*),
    # effects (shadow, opacity, blur), flex/grid (flex-*, grid-*, col-span-*,
    # row-span-*, order, justify-*, items-*, content-*), layout (display
    # keywords as standalone tokens: "flex", "grid", "block", "hidden",
    # "inline-block", ...), position (relative/absolute/fixed/sticky, inset,
    # top/right/bottom/left, z-*), interactivity (cursor-*, pointer-events-*,
    # select-*), transitions (transition, duration-*, ease-*).
}

STANDALONE_TOKENS = {
    "flex", "grid", "block", "inline-block", "inline", "hidden", "grid-inline",
    "relative", "absolute", "fixed", "sticky", "static",
    "italic", "not-italic", "underline", "line-through", "no-underline",
    "uppercase", "lowercase", "capitalize", "normal-case",
    "truncate", "rounded-full",
    # ... etc — every utility that has no variable suffix.
}

RESPONSIVE_PREFIXES = {"sm:", "md:", "lg:", "xl:", "2xl:"}
STATE_PREFIXES = {"hover:", "focus:", "focus-visible:", "active:", "disabled:"}
# A prefix may be chained at most once (e.g. "md:hover:bg-blue-500" — decide
# in Phase 2 whether to allow chaining at all; simplest safe default: allow
# ONE responsive prefix and/or ONE state prefix, not both stacked, to keep
# the validator regex simple. Revisit only if a real page needs it.)

TAILWIND_COLOR_NAMES = {"slate", "gray", "zinc", "neutral", "stone", "red",
    "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan",
    "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose",
    "white", "black", "transparent", "current"}
TAILWIND_SHADE_SCALE = {"50", "100", "200", "300", "400", "500", "600",
                         "700", "800", "900", "950"}
```

Then a validator function:

```python
def is_allowed_tailwind_class(token: str) -> bool:
    """token is one single class string, already split on whitespace."""
```

...implementing, in order:

1. Strip at most one responsive prefix and/or state prefix (from
   `RESPONSIVE_PREFIXES`/`STATE_PREFIXES`); reject if more than one of
   each is present, or if what's left after stripping is empty.
2. If the remainder is in `STANDALONE_TOKENS`, allow.
3. If the remainder matches `{color}-{shade}` (for `bg-`, `text-`,
   `border-` prefixes) against `TAILWIND_COLOR_NAMES`/`TAILWIND_SHADE_SCALE`
   (plus bare `white`/`black`/`transparent`), allow.
4. If the remainder is `{prefix}-{value}` where `prefix` is a key of
   `UTILITY_FAMILIES` and `value` is in that family's allowed set, allow.
5. **Arbitrary value exception** (for CSS variables only, per 1.3): if the
   remainder matches `^(bg|text|border)-\[var\(--[a-z0-9-]+\)\]$`
   (adjust the property-prefix set to whatever `check_css_variable`
   already allows as variable name characters — reuse `CSS_VAR_RE` from
   `sanitize.py` for the `--name` part instead of re-deriving it), allow.
6. Otherwise, reject.

### 3.2 `check_class_list` — the entry point other modules call

```python
MAX_CLASSES_PER_NODE = 20  # bound: same spirit as MAX_STYLE_RULES etc.

def check_class_list(value) -> None:
    """value is whatever came from a node's `attributes.class` — str or
    list of str, per operations.py's existing _validate_class_or_text."""
    tokens = value if isinstance(value, list) else value.split()
    if len(tokens) > MAX_CLASSES_PER_NODE:
        raise SanitizationError("too many classes on one element")
    for token in tokens:
        if not is_allowed_tailwind_class(token):
            raise SanitizationError(f"disallowed Tailwind class: {token}")
```

Wire this into:
- `apps/ai_assistant/operations.py`'s `_validate_class_or_text`, in the
  `attribute == "class"` branch (replaces the current "just check it's
  strings" logic — keep that type check too, call `check_class_list` after).
- `apps/ai_assistant/sanitize.py`'s `check_attributes`, for the `class`
  key specifically (this is what `sanitize_node`/`document_validation.py`
  call for full-document generation and for `add_node`/`replace_node`
  operations).

Both call sites already exist and already see the `class` value — this is
an additive check inside existing branches, not new plumbing.

### 3.3 Safelist generation management command

New file: `apps/editor/management/commands/generate_tailwind_safelist.py`
(standard Django management command). It must:

1. Enumerate every literal class string the allowlist rules in 3.1 can
   produce (expand `UTILITY_FAMILIES`, `STANDALONE_TOKENS`, the color×shade
   cross product, each combined with every entry in `RESPONSIVE_PREFIXES`
   and `STATE_PREFIXES` plus the unprefixed form). This is the same
   "generate all literal strings the rules allow" operation, just run
   forward instead of validating backward — write it as a function in
   `tailwind_classes.py` (e.g. `iter_all_allowed_classes()`) so both the
   validator (3.2) and the generator (3.3) stay in sync by construction —
   **do not hand-maintain two separate lists.**
2. Do **not** attempt to enumerate the CSS-variable arbitrary-value form
   (3.1 step 5) — that's inherently per-document/dynamic, not part of the
   static safelist. It doesn't need to be in the compiled CSS anyway,
   since `bg-[var(--x)]` generates a rule that just says
   `background-color: var(--x)` — Tailwind compiles that utility form
   fine as long as it recognizes the *pattern*, but arbitrary-value
   classes are compiled per-instance already if Tailwind scans them. Since
   these can't be safelisted generically, the practical answer: also emit
   a **fixed, finite set of variable names** into the safelist (the same
   ones `styles.variables` is allowed to contain — check if
   `check_css_variable`/`document_validation.py` already caps allowed
   variable names to a known list; if not, either add that cap now or emit
   the arbitrary-value classes for a small fixed manifest of "well-known"
   variable names used by the global design panel, e.g.
   `--color-primary`, `--color-background`, `--color-text`,
   `--color-surface` — check `templates/editor/editor.html`'s global
   design panel fields (`primaryColor`, `backgroundColor`, `textColor`,
   `surfaceColor`) for the authoritative list of variable names actually
   in use before hardcoding).
3. Write one class string per line to
   `static/editor/.tailwind-safelist.txt` (gitignored, regenerated every
   build).
4. Print a count on success (useful for CI logs / sanity-checking the
   allowlist didn't silently shrink to zero).

### 3.4 Wire the safelist into the Tailwind build

Tailwind v4's CSS entry file (e.g. `static/editor/tailwind-input.css`)
needs:

```css
@import "tailwindcss";
@source "./.tailwind-safelist.txt";
```

(Confirm the exact `@source` directive syntax against the installed
`tailwindcss` version's docs during Phase 1 — v4's source-detection
directives changed across minor versions; do not assume the syntax above
is final without checking `node_modules/tailwindcss/package.json`'s
version and its own docs/CHANGELOG.)

The build command (wire into `package.json`'s `build:css` script):

```bash
uv run python manage.py generate_tailwind_safelist \
  && npx @tailwindcss/cli -i static/editor/tailwind-input.css \
       -o static/editor/tailwind.css --minify
```

---

## 4. Phases — execute in order, commit after each

Each phase must leave `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`, `npm test`, and
`uv run python manage.py check` green before moving to the next. Follow
this repo's existing verification discipline (see git log — every feature
commit this session was preceded by a full gate run and, where UI was
touched, a real Playwright run against a live server, not just unit tests).

### Phase 1 — Build pipeline scaffolding

1. `npm install -D tailwindcss @tailwindcss/cli` (confirm actual package
   names for the version available at execution time — Tailwind's package
   layout has changed between major versions).
2. Create `static/editor/tailwind-input.css` (the `@import`/`@source`
   entry file from 3.4).
3. Create `apps/ai_assistant/tailwind_classes.py` (Section 3.1/3.2) — for
   this phase, a minimal-but-real subset is fine (start with spacing,
   sizing, colors, display, flex — expand as later phases need more; the
   important part is the *mechanism* works end to end first).
4. Create `apps/editor/management/commands/generate_tailwind_safelist.py`
   (needs `apps/editor/management/__init__.py` and
   `apps/editor/management/commands/__init__.py` — standard Django
   package layout, create if absent).
5. Add `build:css` script to `package.json`.
6. **Acceptance check for this phase**: running
   `npm run build:css` from repo root produces
   `static/editor/tailwind.css` containing real compiled utility CSS (grep
   the output file for a couple of expected class selectors, e.g.
   `.flex`, `.p-4` — confirm they're actually present, don't just check
   the file is non-empty).
7. Add `static/editor/tailwind.css` and
   `static/editor/.tailwind-safelist.txt` to `.gitignore`.
8. Commit: `build: scaffold Tailwind CLI build pipeline`.

### Phase 2 — Class allowlist completeness pass

Expand `tailwind_classes.py` to cover everything
`CSS_PROPERTY_ALLOWLIST` (in `sanitize.py`, ~114 properties as of this
writing) covers today, translated to Tailwind-utility equivalents. Go
property-by-property through the current allowlist and make sure there's
a Tailwind path for each concern:

- Colors (`color`, `background-color`, `border-color`, ...) → `text-*`,
  `bg-*`, `border-*` + the CSS-variable arbitrary-value bridge (1.3).
- Spacing (`margin*`, `padding*`, `gap`) → `m-*`/`p-*`/`gap-*` families.
- Sizing (`width`, `height`, `min-*`, `max-*`, `aspect-ratio`) →
  `w-*`/`h-*`/`min-w-*`/`max-w-*`/`min-h-*`/`max-h-*`/`aspect-*`.
- Flexbox/grid (`display`, `flex*`, `justify-content`, `align-*`, `gap*`,
  `grid-template-*`, plus the item-placement properties added this
  session: `grid-column`/`-row`/`-area`, `flex-grow`/`-shrink`/`-basis`,
  `order`) → `flex`/`grid`/`flex-row`/`flex-wrap`/`justify-*`/`items-*`/
  `content-*`/`gap-*`/`grid-cols-*`/`grid-rows-*`/`col-span-*`/
  `row-span-*`/`grow`/`shrink`/`basis-*`/`order-*`.
- Typography (`font*`, `line-height`, `letter-spacing`, `text-align`,
  `text-decoration`, `text-transform`, `text-shadow`, `text-overflow`,
  `-webkit-line-clamp`) → `font-*`/`text-*`/`leading-*`/`tracking-*`/
  `italic`/`underline`/`uppercase`/`truncate`/`line-clamp-*`.
- Visual (`border*`, `border-radius`, `box-shadow`, `opacity`, `filter`,
  `backdrop-filter`, `background-image`, `background-position/-size/
  -repeat`, `background-attachment`, `background-clip`) → `border`/
  `border-*`/`rounded-*`/`shadow-*`/`opacity-*`/`blur-*`/`backdrop-blur-*`/
  `bg-*` (gradient/position/size/repeat utilities — check Tailwind's
  `bg-gradient-to-*`/`from-*`/`via-*`/`to-*` for the gradient case
  specifically, since `background-image` in the current system is mostly
  used for gradients per this session's earlier bugfix history).
- Position (`position`, `top/right/bottom/left`, `inset`, `z-index`) →
  `relative`/`absolute`/`fixed`/`sticky`/`inset-*`/`top-*`/etc/`z-*`.
- Misc (`cursor`, `transition`, `transform`, `object-fit`, `overflow*`,
  `scroll-behavior`, `white-space`, `word-break`, `vertical-align`,
  `box-sizing`, `float`, `clear`) → direct Tailwind equivalents exist for
  all of these; map one-to-one.

For each family added, add it to both `UTILITY_FAMILIES`/
`STANDALONE_TOKENS` (validator) and confirm `iter_all_allowed_classes()`
(generator) produces it — re-run the Phase 1 acceptance check after each
batch.

Add unit tests in a new `tests/test_tailwind_classes.py`:
- A representative allowed class from each family passes
  `is_allowed_tailwind_class`.
- A disallowed/made-up class (`bg-hackery`, `p-999`, `w-[100vw]` with a
  non-var arbitrary value) is rejected.
- A class with two responsive prefixes stacked, or a responsive+state
  combo if you decided against allowing that in 3.1, is rejected.
- The CSS-variable arbitrary-value bridge accepts
  `bg-[var(--color-primary)]` (assuming that's in the well-known variable
  manifest from 3.3.2) and rejects `bg-[var(--anything-else)]` and
  `bg-[url(evil)]`.
- `check_class_list` enforces `MAX_CLASSES_PER_NODE`.

Commit: `feat(ai): flesh out Tailwind class allowlist covering existing CSS property surface`.

### Phase 3 — Wire validation into `operations.py` and `document_validation.py`

1. `apps/ai_assistant/operations.py`: `_validate_class_or_text`'s
   `attribute == "class"` branch calls `check_class_list` after its
   existing type check. Add tests to `tests/test_operations.py`: a
   `set_attribute`/`class` operation with allowed Tailwind classes passes;
   one with a disallowed class string is rejected with
   `OperationValidationError`.
2. `apps/ai_assistant/sanitize.py`: `check_attributes`'s handling of the
   `class` key calls `check_class_list` (for AI-generated full documents,
   via `sanitize_node`). Add tests to whatever test file covers
   `sanitize_node`/`check_attributes` today (check for
   `tests/test_document_validation.py` or an operations test file — this
   session found no dedicated `test_sanitize.py`; add one if the coverage
   doesn't fit naturally elsewhere).
3. Run the **full** existing test suite now — this is the point where
   pre-existing tests using arbitrary class names in fixtures (e.g.
   `"class": ["hero"]`, `"class": ["page"]`, `"class": ["title"]` — seen in
   `tests/test_document_validation.py`, `tests/test_editor_rendering.py`,
   `tests/test_ai_transform.py`) will start failing, because `"hero"`/
   `"page"`/`"title"` are not Tailwind utility classes. **This is expected
   and correct** — update every such fixture to use real Tailwind classes
   instead (e.g. `"hero"` → `["flex", "flex-col", "items-center", "p-8"]`
   or similar; pick whatever's semantically reasonable per test, doesn't
   need to be pixel-perfect, just valid). Cross-reference Section 9's file
   list — don't fix them piecemeal as failures surface, use that section
   as the checklist.

Commit: `feat(ai): enforce Tailwind class allowlist on all class attribute writes`.

### Phase 4 — Rework AI prompts and wizard generation

1. `apps/ai_assistant/prompts.py`:
   - `SYSTEM_PROMPT` (editor transform, line ~36): remove the
     `set_css_declaration`/`set_style_variable` styling instruction (line
     ~55-67, ~78) as the *primary* styling guidance; replace with
     instructions to style via `set_attribute`/`class` using Tailwind
     utility classes, listing (or summarizing) the allowed families from
     `tailwind_classes.py` so the model knows the vocabulary. Keep
     `set_style_variable` mentioned for brand-color-token edits (1.3/1.5).
   - `WIZARD_DOCUMENT_STRUCTURE_PROMPT` (line ~172): today it tells the
     model to give each element "una clase CSS descriptiva" (semantic
     names like "hero", "nav-bar") for the *next* phase to style. Change
     this to: give each element the actual Tailwind utility classes
     directly, inline, as it authors the structure — styling and structure
     become one phase. Update the JSON shape example and the "Reglas
     estrictas" list accordingly. Keep the `available_images`/asset
     handling exactly as shipped this session (`ac75c39`) — unrelated to
     this refactor.
   - `WIZARD_STYLES_PROMPT` (line ~226): re-scope. It no longer writes
     `styles.rules` for element styling (that's now inline in phase 1).
     Decide during implementation whether to keep a (much smaller) second
     call at all — candidates for what it could still usefully do:
     generating `styles.variables` (brand color palette) from the
     description/answers, which today happens as part of the same call.
     If a single merged call reliably produces both a fully-classed body
     tree *and* a small variables object without truncation risk
     (plausible, since output is now much shorter overall — verify
     empirically), **collapse to one call** and delete the second
     `stream_generate` invocation in `wizard_service.py`. This directly
     furthers the "wizard generate reliability" goal (Section 0) — prefer
     collapsing if it works, don't keep two calls out of inertia.
2. `apps/ai_assistant/wizard_service.py`'s `stream_generate_document`:
   - If merging to one call (preferred, see above): restructure so a
     single `stream_generate` call returns `name`, `summary`, `document`
     (with classes already inline), and `styles.variables`. Keep the
     existing post-processing exactly as-is otherwise: `components` forced
     `{}`, `assets` built server-side from `available_images` (unchanged
     from `ac75c39`), then `sanitize_document`.
   - `document_validation.py`'s `_check_styles` still requires
     `styles.rules`/`mediaQueries`/`keyframes` to be present per the schema
     — the wizard should emit them as their empty defaults (`[]`) directly
     rather than omitting them, exactly like `components`/`assets` are
     force-set today. Add this alongside the `components`/`assets`
     force-set lines (currently ~line 220 per this session's most recent
     edit there).
3. Update `tests/test_wizard_service.py` and `tests/test_ai_wizard.py`
   fixtures (`VALID_SKELETON`, `VALID_STYLES`, the `_StubProvider` canned
   responses) to match whatever call-count/shape you land on (one call vs.
   two). If collapsing to one call, `_StubProvider`'s two-canned-response
   pattern (`[structure_response, styles_response]`) needs updating to one
   response — go through every test in these two files, not just the
   "happy path" one.

Commit: `feat(ai): generate Tailwind classes inline during wizard document generation`.

### Phase 5 — Rework the per-element inspector ("Estilo rápido")

In `static/editor/editor-core.js`'s `renderInspector()` (~line 2383):

1. Replace the six raw-text/color-picker "Estilo rápido" fields
   (`nodeBackground`, `nodeColor`, `nodePadding`, `nodeMargin`,
   `nodeWidth`, `nodeTextAlign`) with a small, curated set of Tailwind
   class-toggle controls. Concrete UI pattern (adapt to existing markup
   conventions in this file — grep for `.form-grid`/`.field`/`.control`
   CSS classes already used elsewhere in `editor.css` and match them, do
   not invent a new visual language):
   - Background/text color: a limited swatch picker over
     `TAILWIND_COLOR_NAMES` × a couple of representative shades, PLUS an
     option bound to the project's own `--color-primary`/etc. variables
     (emits `bg-[var(--color-primary)]`).
   - Padding/margin: a stepped slider or a `<select>` over
     `SPACING_SCALE`, emitting `p-{value}`/`m-{value}`.
   - Width: a `<select>` over common `w-*` values (`w-full`, `w-auto`,
     `w-1/2`, `w-1/3`, etc.) — do not try to expose every possible
     fraction, pick the common ones.
   - Text align: keep as a `<select>` (`text-left`/`text-center`/
     `text-right`), same UX as today, different class family.
2. Replace `setInlineStyleProperty`/`getInlineStyle` calls in this
   function with functions that add/remove specific class tokens on
   `node.attributes.class` (a list) — e.g. a `setUtilityClass(node,
   family, newToken)` helper that removes any existing token from the same
   *family* (so setting a new `bg-*` replaces the old `bg-*`, doesn't
   stack both) before pushing the new one. This mirrors `ensureRule`'s
   replace-not-duplicate semantics in `editor-ai.js` conceptually — check
   that file for the pattern already in use, keep it consistent.
3. `setInlineStyleProperty`/`getInlineStyle`/`parseStyleString`/
   `serializeStyle` (lines ~2348-2381) can stay in the file **unused by
   the new inspector** rather than being deleted outright — they may still
   be needed if any other manual-editing surface relies on them (grep for
   all call sites before deciding to delete; if truly orphaned after this
   phase, delete them — don't leave dead code if nothing calls it, per
   this repo's established practice this session of removing confirmed-dead
   code, e.g. commit `b15616f`).
4. The existing "Clases CSS" free-text field (`nodeClasses`, line 2434)
   stays — it's the escape hatch for power users to type Tailwind classes
   directly. Since this write path is a manual edit (not AI), it does not
   go through `check_class_list` today (no validation on manual saves at
   all, per 1.6) — decide whether to add lightweight client-side
   validation/hinting here (nice-to-have, not required for correctness,
   since manual edits are self-trusted) or leave it as free text. Lean
   towards leaving as free text — don't add scope not asked for.

Update `static/editor/editor.css` for whatever new control markup you
introduce (swatch picker, etc.) — follow existing patterns in that file
(same variables, same spacing conventions already visible in
`wizard.css`/`editor.css` from this session's earlier work).

**Manual verification for this phase (required, not optional — see
Section 10)**: run the app for real, select an element, use each new
quick-style control, confirm the class actually lands on
`node.attributes.class`, confirm the preview updates, confirm it survives
save/reload.

Commit: `feat(editor): rework per-element quick-style panel to emit Tailwind classes`.

### Phase 6 — Rendering paths get the compiled CSS `<link>`

1. `static/editor/editor-core.js`'s `buildHtmlDocument()` (the function
   that assembles the full page HTML for preview/export/download): add a
   `<link rel="stylesheet" href="/static/editor/tailwind.css">` (or
   whatever the actual collected-static URL is — use Django's static URL
   helper server-side if this is templated, or hardcode the known path if
   it's pure client-side JS with no template access; check how
   `editor.css`'s own `<link>` is emitted today in `templates/editor/
   editor.html` and mirror it) into the emitted `<head>`, alongside the
   existing `buildCss()`-generated `<style>` tag (legacy rules still need
   to render for old documents — both coexist, Tailwind's compiled
   utilities plus the legacy inline `<style>` block).
2. `apps/editor/rendering.py`'s `thumbnail_srcdoc`: add the same `<link>`
   tag to its returned HTML string's `<head>`, alongside the existing
   inline `<style>` block from `_render_styles`. Gallery/home thumbnails
   need Tailwind's compiled CSS available inside their `<iframe srcdoc>`
   to actually render styled previews — same-origin static file, this
   works fine inside an iframe.
3. Update `tests/test_editor_rendering.py`: add a test asserting the
   `<link>` tag is present in `thumbnail_srcdoc`'s output (don't assert on
   the exact compiled CSS content — that's Tailwind's business, just
   assert the reference is wired in).

Commit: `feat(editor): reference compiled Tailwind CSS in all render paths`.

### Phase 7 — Docker, CI, local dev

1. **`Dockerfile`**: add Node + npm to the `builder` stage (before the
   `uv sync --frozen --no-dev` step or after, either works — Node isn't
   needed at runtime so it must not leak into the `runtime` stage). Run
   `npm install` then `npm run build:css` in the builder stage, so
   `static/editor/tailwind.css` exists on disk before the existing
   `RUN ... collectstatic` step runs (collectstatic must pick up the
   compiled file from `STATICFILES_DIRS`). Confirm with a real
   `docker build` (this repo has done this verification for every Docker-
   touching change this session — do the same here, don't just eyeball the
   Dockerfile).
2. **`.github/workflows/ci.yml`**: add a `Set up Node`/`npm install`/
   `npm run build:css` step before the `pytest` step (Django views/tests
   that render pages referencing the compiled CSS path don't strictly need
   the file to *exist* for most tests, but do this for parity with local
   dev and to catch build breakage in CI). Keep the existing
   `docker-build` job — it now implicitly exercises the Dockerfile change
   from step 1.
3. **`run-local.sh`**: add `npm install && npm run build:css` between
   `uv sync` and `manage.py migrate`/`runserver`. Mention in a comment that
   `npm run build:css -- --watch` (or whatever Tailwind v4's watch flag is)
   is available for active frontend development, without wiring it into
   the default script (the default script is for "get it running", not
   active development — keep it that way, matches how this session's
   `run-local.sh` was scoped originally).
4. **`AGENTS.md`**: update the "Setup" section
   (currently `uv sync` / `docker compose up -d db` / `migrate` /
   `createsuperuser` / `runserver`) to include the `npm install`/
   `build:css` step. Update the "Before calling anything done" gate list
   to mention the Tailwind build as a prerequisite if any test depends on
   it existing.

Commit: `build: wire Tailwind CSS build into Docker, CI, and local setup`.

### Phase 8 — Backward compatibility smoke test

This phase has no code changes — it's a verification gate before calling
the refactor done, given 1.4's "existing data must keep working" promise.

1. Using a fresh local Postgres (via `docker compose up -d db` +
   `migrate`), seed at least one `Template`/`UserTemplate` row with
   **legacy-shaped** `state` (real `styles.rules`/`variables`, semantic
   class names like the pre-refactor fixtures had) — either restore a
   pre-refactor DB dump if one exists, or hand-craft one via
   `manage.py shell` matching the exact shape `VALID_DOCUMENT` fixtures
   had before Phase 3's fixture updates.
2. Open that template in the editor for real (browser). Confirm: it
   renders identically to before (legacy `buildCss()` path engages), the
   gallery thumbnail still renders, undo/redo/save/revisions all still
   work.
3. Confirm the AI transform panel can still *edit* that legacy document
   (e.g. change its text) without erroring, even though it won't add new
   `styles.rules`-based styling to it anymore — a text edit or a
   Tailwind-class-based style addition on top of legacy CSS should both
   work side by side.

Do not skip this phase — it's the concrete proof that 1.4's promise holds,
not just an assertion in a doc.

---

## 5. Target data shape — before / after example

**Before** (today, AI/wizard-generated):

```json
{
  "document": {
    "body": {
      "attributes": {"class": ["page"]},
      "children": [
        {"type": "element", "tag": "h1", "attributes": {"class": ["hero-title"]},
         "children": [{"type": "text", "value": "Bienvenido"}]}
      ]
    }
  },
  "styles": {
    "variables": {"--color-primary": "#5b5ce2"},
    "rules": [
      {"selector": ".page", "declarations": {"display": "flex", "flex-direction": "column"}},
      {"selector": ".hero-title", "declarations": {"color": "var(--color-primary)", "font-size": "48px"}}
    ],
    "mediaQueries": [],
    "keyframes": []
  }
}
```

**After** (new AI/wizard-generated content, post-refactor):

```json
{
  "document": {
    "body": {
      "attributes": {"class": ["flex", "flex-col"]},
      "children": [
        {"type": "element", "tag": "h1",
         "attributes": {"class": ["text-[var(--color-primary)]", "text-5xl", "font-bold"]},
         "children": [{"type": "text", "value": "Bienvenido"}]}
      ]
    }
  },
  "styles": {
    "variables": {"--color-primary": "#5b5ce2"},
    "rules": [],
    "mediaQueries": [],
    "keyframes": []
  }
}
```

Note `styles.variables` unchanged, `styles.rules`/`mediaQueries`/
`keyframes` present but empty (schema-required, per 1.4), all visual
styling now inline on the node via `class`.

---

## 6. Explicitly out of scope

Do not do these as part of this refactor — they are separate concerns,
flag them as new `BACKLOG.md` items instead if they come up:

- **Automatic conversion** of existing `styles.rules`-based documents into
  Tailwind classes. Legacy content keeps rendering via the legacy path
  (1.4) — it is not upgraded.
- **Removing** `set_css_declaration`/`remove_css_declaration`/
  `set_style_variable` operation types, `CSS_PROPERTY_ALLOWLIST`,
  `buildCss()`, or any other legacy-rendering machinery. It all stays,
  permanently, for backward compatibility.
- **Dark mode / Tailwind theming beyond CSS variables.** Out of scope —
  the brand-color-token bridge (1.3) is the only theming mechanism this
  refactor introduces.
- **Component library adoption** (shadcn/ui, daisyUI, etc.) on top of
  Tailwind. Not requested, not in scope.
- **Rewriting the JSON "advanced" tab** (`#sectionModal`'s `data-panel=
  "json"`) — it shows raw `state` JSON regardless of shape; no changes
  needed there.
- **Changing `AI_MAX_OPERATIONS`/`AI_MAX_INPUT_CHARACTERS`/token budgets**
  — if generation gets meaningfully cheaper (Section 0's stated goal),
  that's a nice side effect to note in the final report, not something to
  proactively re-tune without evidence.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Tailwind CLI's `@source`/safelist syntax differs from what's drafted in 3.4 (version drift) | Phase 1's acceptance check (grep compiled output for expected selectors) catches this immediately — don't proceed past Phase 1 until it's confirmed working. |
| The class-allowlist regex/rule design in Section 3 is incomplete for some real generation need | Expected and fine — it's designed to be extended the same way `CSS_PROPERTY_ALLOWLIST` was extended this session (concrete need → add the family/token → test → done). Not a blocker to shipping the refactor. |
| Existing UserTemplate/Project rows break after this change | Phase 8 exists specifically to catch this before declaring done. |
| Wizard's two-phase-to-one-phase merge (Phase 4) makes generation *less* reliable instead of more | Keep the two-phase structure if a single call proves flaky in testing — the merge is a "prefer if it works" optimization (Section 4, Phase 4), not a hard requirement of this refactor. The hard requirement is classes-inline-in-structure; the call-count is a judgment call to make with real generation attempts, not a coin flip. |
| CSP breaks because of how the Tailwind `<link>` or safelist file gets served | It's a same-origin static file link, no inline script — should not affect CSP at all. If it does, that's a sign something was implemented wrong (e.g. accidentally using the Play CDN script), not a reason to loosen CSP. |

---

## 8. Final report requirements

When this refactor is complete, produce a summary (same format used at the
end of prior work in this session) covering:

- Every phase's commit hash and one-line summary.
- Final `CSS_PROPERTY_ALLOWLIST`-equivalent coverage: which Tailwind
  utility families ended up supported, any explicitly dropped (with why).
- Whether the wizard generation call count ended up 1 or 2 phases, and why.
- Test count before/after (this session ended at 120 passing — report the
  new total).
- Confirmation Phase 8's backward-compatibility check was actually run,
  not assumed.
- Any deviation from this document, and why.
