"""Security allowlists and node/CSS/URL sanitization for editor documents.

Everything the AI (or the browser) sends is untrusted. These checks are the
single source of truth for what a node tree may contain. They are used both
to validate the incoming selected node and the operations the AI returns.
"""

from __future__ import annotations

import re

TAG_RE = re.compile(r"^[a-z][a-z0-9-]*$")

FORBIDDEN_TAGS = {"script", "iframe", "object", "embed", "applet", "base"}
FORBIDDEN_ATTRS = {"srcdoc", "nonce", "integrity"}

# Attributes whose value is a URL and therefore needs scheme checking.
URL_ATTRS = {"href", "src", "action", "formaction", "poster", "cite", "background"}
SAFE_URL_SCHEMES = {"http", "https", "mailto", "tel"}

# CSS property allowlist. Anything outside this set is rejected.
CSS_PROPERTY_ALLOWLIST = {
    "color",
    "background",
    "background-color",
    "background-image",
    "background-attachment",
    "background-clip",
    "-webkit-background-clip",
    "-webkit-text-fill-color",
    "-webkit-font-smoothing",
    "backdrop-filter",
    "border",
    "border-color",
    "border-width",
    "border-style",
    "border-radius",
    "border-top",
    "border-right",
    "border-bottom",
    "border-left",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "width",
    "height",
    "min-width",
    "max-width",
    "min-height",
    "max-height",
    "display",
    "flex",
    "flex-direction",
    "flex-wrap",
    "justify-content",
    "align-items",
    "align-content",
    "align-self",
    "gap",
    "row-gap",
    "column-gap",
    "grid-template-columns",
    "grid-template-rows",
    "font",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "line-height",
    "letter-spacing",
    "text-align",
    "text-decoration",
    "text-transform",
    "text-shadow",
    "box-shadow",
    "opacity",
    "position",
    "top",
    "right",
    "bottom",
    "left",
    "z-index",
    "overflow",
    "overflow-x",
    "overflow-y",
    "scroll-behavior",
    "cursor",
    "transition",
    "transform",
    "object-fit",
    "list-style",
    "white-space",
    "word-break",
    "vertical-align",
    "box-sizing",
    "aspect-ratio",
}

# CSS values must not smuggle in code or external fetches.
CSS_VALUE_FORBIDDEN = re.compile(
    r"(expression\s*\(|javascript:|@import|url\s*\(\s*[\"']?\s*(?!#|/|data:image/))",
    re.IGNORECASE,
)

# Limits on the incoming node subtree.
MAX_NODE_DEPTH = 40
MAX_NODE_COUNT = 2000
MAX_TEXT_LENGTH = 20000

# Limits on a full generated document's styles block (see document_validation.py).
MAX_STYLE_VARIABLES = 100
MAX_STYLE_RULES = 200
MAX_MEDIA_QUERIES = 10

CSS_VAR_RE = re.compile(r"^--[a-z0-9-]+$", re.IGNORECASE)
# CSS selectors are interpolated directly into a stylesheet string client-side
# (editor-core.js's ensureRule) — block characters that could break out of a
# selector into raw CSS/HTML.
CSS_SELECTOR_FORBIDDEN = re.compile(r"[<>{};]")
# A media query is interpolated raw into `@media <query> { ... }`
# (editor-core.js's buildCss) — allowlist instead of denylist since this sits
# right next to the `{` that opens a nested block.
CSS_MEDIA_QUERY_ALLOWED = re.compile(r"^[a-zA-Z0-9\s(),.:-]+$")


class SanitizationError(ValueError):
    """Raised when untrusted content violates a security rule."""


def check_attribute_name(name: str) -> None:
    lowered = str(name).strip().lower()
    if not lowered:
        raise SanitizationError("empty attribute name")
    if lowered.startswith("on"):
        raise SanitizationError(f"event handler attribute not allowed: {name}")
    if lowered in FORBIDDEN_ATTRS:
        raise SanitizationError(f"attribute not allowed: {name}")


def check_url_value(value: str) -> None:
    raw = str(value).strip()
    if not raw:
        return
    lowered = raw.lower()
    # Relative URLs and same-page anchors are fine.
    if raw.startswith(("#", "/", "./", "../")):
        return
    if lowered.startswith("data:text/html") or lowered.startswith("javascript:"):
        raise SanitizationError(f"unsafe URL: {value}")
    if ":" in raw.split("/", 1)[0]:
        scheme = lowered.split(":", 1)[0]
        if scheme not in SAFE_URL_SCHEMES:
            raise SanitizationError(f"unsafe URL scheme: {scheme}")


def check_css_declaration(prop: str, value: str) -> None:
    name = str(prop).strip().lower()
    if name not in CSS_PROPERTY_ALLOWLIST:
        raise SanitizationError(f"CSS property not allowed: {prop}")
    if CSS_VALUE_FORBIDDEN.search(str(value)):
        raise SanitizationError(f"CSS value not allowed for {prop}")


def check_css_variable(name: str, value: str) -> None:
    if not isinstance(name, str) or not CSS_VAR_RE.match(name):
        raise SanitizationError(f"invalid CSS variable name: {name}")
    if not isinstance(value, str):
        raise SanitizationError("CSS variable value must be a string")
    if CSS_VALUE_FORBIDDEN.search(value):
        raise SanitizationError(f"unsafe CSS variable value: {value}")


def check_css_selector(selector: str) -> None:
    if not isinstance(selector, str) or not selector.strip():
        raise SanitizationError("selector required")
    if CSS_SELECTOR_FORBIDDEN.search(selector):
        raise SanitizationError(f"unsafe CSS selector: {selector}")


def check_css_media_query(query: str) -> None:
    if not isinstance(query, str) or not query.strip():
        raise SanitizationError("media query required")
    if not CSS_MEDIA_QUERY_ALLOWED.match(query):
        raise SanitizationError(f"unsafe media query: {query}")


def check_attributes(attributes: dict) -> None:
    if not isinstance(attributes, dict):
        raise SanitizationError("attributes must be an object")
    for name, value in attributes.items():
        check_attribute_name(name)
        lowered = str(name).strip().lower()
        if lowered == "style":
            raise SanitizationError("inline style attribute not allowed")
        if lowered in URL_ATTRS:
            check_url_value(value)


def sanitize_node(node, *, _depth=0, _counter=None) -> None:
    """Validate a single node tree; raise SanitizationError on any violation."""
    if _counter is None:
        _counter = [0]
    _counter[0] += 1
    if _counter[0] > MAX_NODE_COUNT:
        raise SanitizationError("node tree too large")
    if _depth > MAX_NODE_DEPTH:
        raise SanitizationError("node tree too deep")

    if not isinstance(node, dict):
        raise SanitizationError("node must be an object")

    node_type = node.get("type")
    if node_type == "text":
        value = node.get("value", "")
        if not isinstance(value, str):
            raise SanitizationError("text value must be a string")
        if len(value) > MAX_TEXT_LENGTH:
            raise SanitizationError("text value too long")
        return
    if node_type != "element":
        raise SanitizationError(f"unknown node type: {node_type}")

    tag = str(node.get("tag", "")).lower()
    if not TAG_RE.match(tag):
        raise SanitizationError(f"invalid tag: {node.get('tag')}")
    if tag in FORBIDDEN_TAGS:
        raise SanitizationError(f"tag not allowed: {tag}")

    check_attributes(node.get("attributes", {}) or {})

    children = node.get("children", [])
    if children and not isinstance(children, list):
        raise SanitizationError("children must be a list")
    for child in children or []:
        sanitize_node(child, _depth=_depth + 1, _counter=_counter)
