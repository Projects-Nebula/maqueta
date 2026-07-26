"""Convert pasted external HTML into a sanitized editor node.

Not AI-authored — this is a deterministic, synchronous converter. It routes
through the exact same sanitize_node gate as AI-authored operations
(apps/ai_assistant/operations.py's add_node), so imported content gets no
new trust boundary. Structure only: the raw `class` attribute is always
dropped (imported classes almost never match the Tailwind allowlist, and
check_attributes would otherwise reject the whole import over one disallowed
class), but a small allowlisted set of common `style` declarations is mapped
to their exact Tailwind equivalent (STYLE_TO_TAILWIND) — never a general
CSS-to-Tailwind conversion, only known exact property:value matches, each
still re-validated through is_allowed_tailwind_class before being kept.
Everything else in `style` (and every other unlisted attribute) is dropped.
"""

from __future__ import annotations

from html.parser import HTMLParser

from .sanitize import SanitizationError, sanitize_node
from .tailwind_classes import is_allowed_tailwind_class

MAX_IMPORT_HTML_LENGTH = 50_000

# Attributes worth keeping verbatim from imported markup — everything else
# (id, data-*, event handlers, ...) is dropped, not just "not copied":
# check_attribute_name already rejects on* handlers. `class` and `style` are
# handled separately (see STYLE_TO_TAILWIND) rather than kept verbatim.
KEPT_ATTRS = {"href", "src", "alt", "title", "target", "rel"}

# Exact (property, value) matches only — small and deliberately conservative.
# Add entries here as real imports show a common pattern worth mapping;
# resist growing this into a general CSS-to-Tailwind converter.
STYLE_TO_TAILWIND = {
    ("text-align", "center"): "text-center",
    ("text-align", "left"): "text-left",
    ("text-align", "right"): "text-right",
    ("font-weight", "bold"): "font-bold",
    ("font-weight", "700"): "font-bold",
    ("font-weight", "normal"): "font-normal",
    ("font-weight", "400"): "font-normal",
    ("font-style", "italic"): "italic",
    ("text-decoration", "underline"): "underline",
    ("text-decoration", "none"): "no-underline",
}


def _mapped_classes_and_skipped(style_value: str) -> tuple[list[str], int]:
    """Map a `style="..."` value's declarations through STYLE_TO_TAILWIND.

    Returns (mapped_classes, skipped_declaration_count) — skipped counts
    every declaration that had no exact mapping, so the caller's
    skipped_attributes total reflects what's still actually dropped.
    """
    classes = []
    skipped = 0
    for chunk in style_value.split(";"):
        if ":" not in chunk:
            continue
        prop, _, value = chunk.partition(":")
        tw_class = STYLE_TO_TAILWIND.get((prop.strip().lower(), value.strip().lower()))
        if tw_class and is_allowed_tailwind_class(tw_class):
            classes.append(tw_class)
        else:
            skipped += 1
    return classes, skipped


VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class HtmlImportError(ValueError):
    """Raised when the pasted HTML is empty, too long, or fails sanitization."""


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"type": "element", "tag": "div", "attributes": {}, "children": []}
        self.stack = [self.root]
        self.skipped_attrs = 0

    def _make_node(self, tag, attrs):
        node = {"type": "element", "tag": tag.lower(), "attributes": {}, "children": []}
        classes = []
        for name, value in attrs:
            name = name.lower()
            if name in KEPT_ATTRS and value is not None:
                node["attributes"][name] = value
            elif name == "class":
                self.skipped_attrs += 1
            elif name == "style" and value:
                mapped, skipped = _mapped_classes_and_skipped(value)
                classes.extend(mapped)
                self.skipped_attrs += skipped
        if classes:
            node["attributes"]["class"] = classes
        return node

    def handle_starttag(self, tag, attrs):
        node = self._make_node(tag, attrs)
        self.stack[-1]["children"].append(node)
        if tag.lower() not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1]["children"].append(self._make_node(tag, attrs))

    def handle_endtag(self, tag):
        if len(self.stack) > 1:
            self.stack.pop()

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.stack[-1]["children"].append({"type": "text", "value": text})


def html_to_node(html: str) -> tuple[dict, int]:
    """Return (sanitized_node, skipped_attribute_count).

    Raises HtmlImportError if the input is empty/too long, or if the
    resulting node tree fails sanitize_node (e.g. a forbidden tag).
    """
    if not isinstance(html, str) or not html.strip():
        raise HtmlImportError("empty HTML")
    if len(html) > MAX_IMPORT_HTML_LENGTH:
        raise HtmlImportError("HTML too long")

    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()

    try:
        sanitize_node(builder.root)
    except SanitizationError as exc:
        raise HtmlImportError(str(exc)) from exc

    return builder.root, builder.skipped_attrs
