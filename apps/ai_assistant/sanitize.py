"""Security allowlists and node/CSS/URL sanitization for editor documents.

Everything the AI (or the browser) sends is untrusted. These checks are the
single source of truth for what a node tree may contain. They are used both
to validate the incoming selected node and the operations the AI returns.
"""

from __future__ import annotations

import re

TAG_RE = re.compile(r"^[a-z][a-z0-9-]*$")

FORBIDDEN_TAGS = {"script", "object", "embed", "applet", "base"}
FORBIDDEN_ATTRS = {"srcdoc", "nonce", "integrity"}

# iframe is otherwise forbidden (arbitrary iframe src on a publicly published
# page is a clickjacking/phishing vector), but video embeds are a legitimate,
# common request — allow iframe only with a src on one of these known video
# providers' embed paths.
IFRAME_SRC_ALLOWED_PREFIXES = (
    "https://www.youtube.com/embed/",
    "https://www.youtube-nocookie.com/embed/",
    "https://player.vimeo.com/video/",
)

# Attributes whose value is a URL and therefore needs scheme checking.
URL_ATTRS = {"href", "src", "action", "formaction", "poster", "cite", "background"}
SAFE_URL_SCHEMES = {"http", "https", "mailto", "tel"}

# state.assets may only reference the app's own uploaded-image storage (never
# an arbitrary external URL) — keep in sync with settings.MEDIA_URL. Not
# imported from Django settings to keep this module dependency-free.
ASSET_URL_PREFIX = "/media/"
MAX_ASSETS = 20
MAX_ASSET_DIMENSION = 4000

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
    "background-position",
    "background-size",
    "background-repeat",
    "inset",
    "filter",
    "outline",
    "outline-color",
    "outline-offset",
    "text-overflow",
    "-webkit-line-clamp",
    "-webkit-box-orient",
    "grid-column",
    "grid-row",
    "grid-area",
    "grid-template-areas",
    "flex-grow",
    "flex-shrink",
    "flex-basis",
    "order",
    "float",
    "clear",
}

# CSS values must not smuggle in code or external fetches.
CSS_VALUE_FORBIDDEN = re.compile(
    r"(expression\s*\(|javascript:|@import|url\s*\(\s*[\"']?\s*(?!#|/|data:image/)|[<>{}])",
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


def check_asset_entry(asset_id: str, entry: dict) -> None:
    if not isinstance(asset_id, str) or not asset_id.strip():
        raise SanitizationError("asset id required")
    if not isinstance(entry, dict) or set(entry.keys()) != {"url", "width", "height"}:
        raise SanitizationError(f"unexpected keys in asset entry: {asset_id}")
    url = entry.get("url")
    if not isinstance(url, str) or not url.startswith(ASSET_URL_PREFIX):
        raise SanitizationError(f"asset url must be an uploaded asset: {asset_id}")
    check_url_value(url)
    for dim in ("width", "height"):
        value = entry.get(dim)
        valid = isinstance(value, int) and not isinstance(value, bool)
        valid = valid and 0 < value <= MAX_ASSET_DIMENSION
        if not valid:
            raise SanitizationError(f"invalid asset {dim}: {asset_id}")


def check_attributes(attributes: dict) -> None:
    # Deferred import: tailwind_classes.py imports SanitizationError from
    # this module, so importing it back at module level here would be
    # circular. By the time this function actually runs, both modules are
    # fully loaded.
    from .tailwind_classes import check_class_list

    if not isinstance(attributes, dict):
        raise SanitizationError("attributes must be an object")
    for name, value in attributes.items():
        check_attribute_name(name)
        lowered = str(name).strip().lower()
        if lowered == "style":
            raise SanitizationError("inline style attribute not allowed")
        if lowered in URL_ATTRS:
            check_url_value(value)
        if lowered == "class":
            check_class_list(value)
        if lowered in ("data-product-id", "data-buy-form"):
            # A product-card reference (FEATURE.md) — just an id, never a
            # URL/selector, so a strict digits-only check is enough.
            if not isinstance(value, str) or not value.isdigit():
                raise SanitizationError(f"{name} must be a digit string")


def _normalize_context_node(node, *, _depth=0, _counter=None):
    """Copy a node tree while removing legacy classes from AI context.

    Existing saved pages can still use semantic classes backed by
    ``styles.rules``. Those classes must not be mistaken for valid Tailwind
    output, but they also must not make an otherwise safe selected node
    unusable as model context.
    """
    if _counter is None:
        _counter = [0]
    _counter[0] += 1
    if _counter[0] > MAX_NODE_COUNT:
        raise SanitizationError("node tree too large")
    if _depth > MAX_NODE_DEPTH:
        raise SanitizationError("node tree too deep")
    if not isinstance(node, dict):
        return node

    normalized = dict(node)
    if node.get("type") != "element":
        return normalized

    attributes = node.get("attributes")
    if isinstance(attributes, dict) and "class" in attributes:
        from .tailwind_classes import normalize_context_class_list

        normalized_attributes = dict(attributes)
        class_value = normalize_context_class_list(attributes["class"])
        if class_value:
            normalized_attributes["class"] = class_value
        else:
            normalized_attributes.pop("class")
        normalized["attributes"] = normalized_attributes

    children = node.get("children")
    if isinstance(children, list):
        normalized["children"] = [
            _normalize_context_node(child, _depth=_depth + 1, _counter=_counter)
            for child in children
        ]
    return normalized


def sanitize_context_node(node) -> dict:
    """Validate and return a selected node safe to send as AI context.

    This intentionally differs from ``sanitize_node`` only for legacy class
    tokens. All structural, tag, attribute, URL, iframe, size, and depth
    checks still use the same strict validator after normalization.
    """
    normalized = _normalize_context_node(node)
    sanitize_node(normalized)
    return normalized


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

    attributes = node.get("attributes", {}) or {}
    if tag == "iframe":
        src = str(attributes.get("src", ""))
        if not src.startswith(IFRAME_SRC_ALLOWED_PREFIXES):
            raise SanitizationError(f"iframe src not allowed: {src}")

    check_attributes(attributes)

    children = node.get("children", [])
    if children and not isinstance(children, list):
        raise SanitizationError("children must be a list")
    for child in children or []:
        sanitize_node(child, _depth=_depth + 1, _counter=_counter)
