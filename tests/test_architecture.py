"""Structural invariants documented in openspec/project.md's gotchas.

These exist so a violation fails CI immediately instead of surfacing later as
a silently-broken page (CSP blocks inline scripts with no console error).
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
EDITOR_CORE_JS = STATIC_DIR / "editor" / "editor-core.js"

# Matches a <script ...> tag that has no src= attribute. type="application/json"
# data blocks are inert and fine; anything else is executable JS and is
# silently blocked by the CSP `script-src 'self'` (no `'unsafe-inline'`).
INLINE_SCRIPT_RE = re.compile(
    r"<script(?![^>]*\bsrc=)(?![^>]*type=[\"']application/json[\"'])[^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)

SECRET_ENV_VAR_NAMES = ("OPENAI_API_KEY", "OPENCODE_ZEN_API_KEY")


def _html_templates():
    return sorted(TEMPLATES_DIR.rglob("*.html"))


def test_no_inline_executable_scripts_in_templates():
    offenders = []
    for path in _html_templates():
        text = path.read_text(encoding="utf-8")
        for match in INLINE_SCRIPT_RE.finditer(text):
            body = match.group(1).strip()
            if body:
                offenders.append(str(path.relative_to(BASE_DIR)))
    assert not offenders, (
        "Inline <script> with executable JS is silently blocked by CSP "
        f"(script-src 'self'): {offenders}. Move the logic to a static/*.js "
        "file and load it with <script src=...>."
    )


def test_no_ai_provider_secrets_referenced_in_frontend_js():
    offenders = []
    for path in sorted(STATIC_DIR.rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        for name in SECRET_ENV_VAR_NAMES:
            if name in text:
                offenders.append(f"{path.relative_to(BASE_DIR)}: {name}")
    assert not offenders, (
        f"AI provider secret referenced in frontend JS: {offenders}. "
        "These must never reach the browser."
    )


def test_editor_core_facade_stays_appended_at_the_end():
    """window.EditorCore must stay the facade appended at the IIFE's end.

    editor-core.js is the original editor.html IIFE verbatim; the facade is
    intentionally the last thing added, not spliced into the middle of the
    original body. See openspec/project.md's gotchas.
    """
    lines = EDITOR_CORE_JS.read_text(encoding="utf-8").splitlines()
    facade_line_indexes = [i for i, line in enumerate(lines) if "window.EditorCore = {" in line]
    assert facade_line_indexes, "window.EditorCore facade assignment not found"
    facade_index = facade_line_indexes[0]
    assert facade_index / len(lines) > 0.9, (
        "window.EditorCore facade has moved away from the end of the file — "
        "it must stay appended after the original IIFE body, never spliced "
        "into the middle of it."
    )
