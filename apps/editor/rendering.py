"""Server-side mini-render of a template's `state` JSON for gallery thumbnails.

Deliberately does not reuse the client-side `buildHtmlDocument` in
editor-core.js (that IIFE is left untouched, see CLAUDE.md) — this is a much
smaller, read-only subset: no scripts, no head metadata, just body markup +
styles, enough for a scaled-down preview.
"""

from html import escape


def _render_attributes(attributes: dict) -> str:
    parts = []
    for name, value in attributes.items():
        if isinstance(value, list):
            value = " ".join(str(v) for v in value)
        parts.append(f'{escape(str(name))}="{escape(str(value))}"')
    return (" " + " ".join(parts)) if parts else ""


def _render_node(node: dict) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return escape(str(node.get("value", "")))
    if node.get("type") != "element":
        return ""
    tag = node.get("tag")
    if not isinstance(tag, str) or not tag:
        return ""
    tag = escape(tag)
    attrs = _render_attributes(node.get("attributes") or {})
    children = "".join(_render_node(child) for child in node.get("children") or [])
    return f"<{tag}{attrs}>{children}</{tag}>"


def _render_styles(styles: dict) -> str:
    variables = styles.get("variables") or {}
    rules = styles.get("rules") or []
    lines = []
    if variables:
        var_decls = "; ".join(f"{name}: {value}" for name, value in variables.items())
        lines.append(f":root {{ {var_decls} }}")
    for rule in rules:
        selector = rule.get("selector")
        declarations = rule.get("declarations") or {}
        if not selector or not declarations:
            continue
        decls = "; ".join(f"{prop}: {value}" for prop, value in declarations.items())
        lines.append(f"{selector} {{ {decls} }}")
    return "\n".join(lines)


def thumbnail_srcdoc(state: dict | None) -> str | None:
    """Build a standalone HTML document from `state` for an `<iframe srcdoc>`
    thumbnail. Returns None when there's no renderable body (falls back to
    the plain first-letter avatar in the template)."""
    if not isinstance(state, dict):
        return None
    document = state.get("document") or {}
    body = document.get("body") or {}
    children = body.get("children") or []
    if not children:
        return None

    body_html = "".join(_render_node(child) for child in children)
    css = _render_styles(state.get("styles") or {})

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        f"<style>body {{ margin: 0; }} {css}</style>"
        f"</head><body>{body_html}</body></html>"
    )
