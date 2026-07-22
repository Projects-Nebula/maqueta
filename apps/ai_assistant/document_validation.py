"""Validation of a FULL page document generated from scratch by the AI.

Distinct from operations.py (which validates incremental edit operations
against an existing page): this validates an entire document tree — used by
the template-creation wizard, where the AI has no prior human-authored state
to constrain it. Nothing here is trusted; a violation anywhere rejects the
whole document rather than silently dropping the offending part.

The single most load-bearing check in this module is settings.allowRawHtml /
settings.allowInlineScripts and document.head.scripts: if the AI ever set
those to anything other than their fixed safe values, it would reopen exactly
the injection surface sanitize.py's node-tree checks are designed to close.
"""

from __future__ import annotations

from .sanitize import (
    MAX_MEDIA_QUERIES,
    MAX_STYLE_RULES,
    MAX_STYLE_VARIABLES,
    SanitizationError,
    check_css_declaration,
    check_css_media_query,
    check_css_selector,
    check_css_variable,
    sanitize_node,
)

MAX_TITLE_LENGTH = 200
MAX_META_COUNT = 10
MAX_META_VALUE_LENGTH = 300

# The AI is told to always emit these exact values (see prompts.py). Anything
# else is rejected outright — these flags gate whether raw HTML/scripts are
# ever allowed to reach the page, so they are never AI-decided.
REQUIRED_SETTINGS = {
    "strict": True,
    "escapeText": True,
    "allowRawHtml": False,
    "allowInlineScripts": False,
    "requireImageAlt": True,
    "requireUniqueIds": True,
}

REQUIRED_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "settings",
    "document",
    "styles",
    "components",
    "assets",
}


class DocumentValidationError(ValueError):
    """Raised when an AI-generated full document is malformed or unsafe."""


def _require(condition, message):
    if not condition:
        raise DocumentValidationError(message)


def _check_settings(settings):
    _require(isinstance(settings, dict), "settings must be an object")
    for key, expected in REQUIRED_SETTINGS.items():
        _require(settings.get(key) is expected, f"settings.{key} must be {expected}")


def _check_head(head):
    _require(isinstance(head, dict), "document.head must be an object")

    title = head.get("title", "")
    _require(
        isinstance(title, str) and len(title) <= MAX_TITLE_LENGTH,
        "invalid document.head.title",
    )

    metas = head.get("metas", [])
    _require(
        isinstance(metas, list) and len(metas) <= MAX_META_COUNT,
        "too many document.head.metas",
    )
    for meta in metas:
        _require(isinstance(meta, dict), "each meta must be an object")
        _require("http-equiv" not in meta, "meta http-equiv is not allowed")
        for key, value in meta.items():
            _require(key in ("charset", "name", "content"), f"meta key not allowed: {key}")
            _require(
                isinstance(value, str) and len(value) <= MAX_META_VALUE_LENGTH,
                f"invalid meta value for {key}",
            )

    # No legitimate use case for AI-authored <link>/<script> tags — both are
    # unnecessary attack surface (third-party fetch, arbitrary code) with zero
    # payoff for a generated landing page.
    _require(head.get("links", []) == [], "document.head.links must be empty")
    _require(head.get("scripts", []) == [], "document.head.scripts must be empty")


def _check_html_attributes(attrs):
    _require(isinstance(attrs, dict), "document.htmlAttributes must be an object")
    lang = attrs.get("lang", "")
    lang_ok = isinstance(lang, str) and 2 <= len(lang) <= 10 and lang.replace("-", "").isalpha()
    _require(lang_ok, "invalid lang")
    _require(attrs.get("dir") in ("ltr", "rtl"), "invalid dir")


def _check_rule_list(rules, *, label):
    _require(isinstance(rules, list), f"{label} must be a list")
    _require(len(rules) <= MAX_STYLE_RULES, f"too many rules in {label}")
    for rule in rules:
        _require(isinstance(rule, dict), f"each rule in {label} must be an object")
        _require(
            set(rule.keys()) == {"selector", "declarations"},
            f"unexpected keys in {label} rule: {sorted(rule.keys())}",
        )
        check_css_selector(rule.get("selector"))
        declarations = rule.get("declarations", {})
        _require(isinstance(declarations, dict), f"{label} rule declarations must be an object")
        for prop, value in declarations.items():
            check_css_declaration(prop, value)


def _check_styles(styles):
    _require(isinstance(styles, dict), "styles must be an object")

    variables = styles.get("variables", {})
    _require(isinstance(variables, dict), "styles.variables must be an object")
    _require(len(variables) <= MAX_STYLE_VARIABLES, "too many style variables")
    for name, value in variables.items():
        check_css_variable(name, value)

    _check_rule_list(styles.get("rules", []), label="styles.rules")

    # Rules nested under a single, validated media-query condition — the
    # only form of responsiveness the AI can express (prompts.py).
    media_queries = styles.get("mediaQueries", [])
    _require(isinstance(media_queries, list), "styles.mediaQueries must be a list")
    _require(len(media_queries) <= MAX_MEDIA_QUERIES, "too many media queries")
    for group in media_queries:
        _require(isinstance(group, dict), "each media query group must be an object")
        _require(
            set(group.keys()) == {"query", "rules"},
            f"unexpected keys in media query group: {sorted(group.keys())}",
        )
        check_css_media_query(group.get("query"))
        _check_rule_list(group.get("rules", []), label="a styles.mediaQueries group")

    # Keyframes add selector-injection-style surface (percentage steps, nested
    # declarations) for no real payoff on a first-generation static page —
    # forced empty for now; the AI is told not to populate this (prompts.py).
    _require(styles.get("keyframes", []) == [], "styles.keyframes must be empty")


def _validate(state: dict) -> None:
    _require(isinstance(state, dict), "document must be an object")
    _require(
        set(state.keys()) == REQUIRED_TOP_LEVEL_KEYS,
        f"unexpected top-level document keys: {sorted(state.keys())}",
    )
    _require(state.get("schemaVersion") == "2.0", "unsupported schemaVersion")

    _check_settings(state.get("settings"))

    document = state.get("document")
    _require(isinstance(document, dict), "document.document must be an object")
    # A malformed/truncated response (including a json-repair salvage of one)
    # can close an object early and leave what should be nested content as
    # dangling sibling keys one level up instead — e.g. a whole extra section
    # silently missing from body.children, reappearing as stray
    # type/tag/attributes/children keys on document itself. Catching that
    # here, structurally, is more reliable than hoping every such slip also
    # happens to trip an unrelated check (like an unlisted CSS property).
    _require(
        set(document.keys()) == {"doctype", "htmlAttributes", "head", "body"},
        f"unexpected keys in document.document: {sorted(document.keys())}",
    )
    _require(document.get("doctype") == "html", "unsupported doctype")
    _check_html_attributes(document.get("htmlAttributes", {}))
    _check_head(document.get("head", {}))

    body = document.get("body")
    _require(isinstance(body, dict), "document.body must be an object")
    _require(
        set(body.keys()) == {"attributes", "children"},
        f"unexpected keys in document.body: {sorted(body.keys())}",
    )
    sanitize_node(
        {
            "type": "element",
            "tag": "body",
            "attributes": body.get("attributes", {}) or {},
            "children": body.get("children", []) or [],
        }
    )

    _check_styles(state.get("styles", {}))

    # No image-upload feature yet (phase 2) — nothing legitimate can populate
    # these, so any non-empty value means the AI hallucinated content it
    # shouldn't reference.
    _require(state.get("components") == {}, "components must be empty")
    _require(state.get("assets") == {}, "assets must be empty")


def sanitize_document(state: dict) -> None:
    """Validate a full AI-generated page document. Raises or returns None."""
    try:
        _validate(state)
    except SanitizationError as exc:
        raise DocumentValidationError(str(exc)) from exc
