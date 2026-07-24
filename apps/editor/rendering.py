"""Server-side rendering of a template's `state` JSON, outside the editor.

Two renderers sharing the same node/style helpers: `thumbnail_srcdoc` (a
small, head-metadata-free subset for gallery card previews) and
`public_page_html` (a full standalone document for a published template's
public page, FEATURE.md). Neither reuses the client-side `buildHtmlDocument`
in editor-core.js (that IIFE is left untouched, see CLAUDE.md) and neither
ever includes an editor script — both are read-only.
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


def _render_rule_list(rules) -> list[str]:
    lines = []
    for rule in rules or []:
        selector = rule.get("selector")
        declarations = rule.get("declarations") or {}
        if not selector or not declarations:
            continue
        decls = "; ".join(f"{prop}: {value}" for prop, value in declarations.items())
        lines.append(f"{selector} {{ {decls} }}")
    return lines


def _render_styles(styles: dict) -> str:
    variables = styles.get("variables") or {}
    lines = []
    if variables:
        var_decls = "; ".join(f"{name}: {value}" for name, value in variables.items())
        lines.append(f":root {{ {var_decls} }}")
    lines.extend(_render_rule_list(styles.get("rules")))
    for group in styles.get("mediaQueries") or []:
        query = group.get("query")
        nested = _render_rule_list(group.get("rules"))
        if not query or not nested:
            continue
        lines.append(f"@media {query} {{ {' '.join(nested)} }}")
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
        '<link rel="stylesheet" href="/static/editor/tailwind.css">'
        f"<style>body {{ margin: 0; }} {css}</style>"
        f"</head><body>{body_html}</body></html>"
    )


def public_page_html(
    state: dict | None,
    *,
    title_fallback: str = "Página",
    analytics_template_slug: str | None = None,
) -> str | None:
    """Full standalone HTML document for a published UserTemplate's public
    page (FEATURE.md 1.2) — unlike thumbnail_srcdoc, includes real <head>
    metadata (doctype, htmlAttributes, metas, title) since this is the
    actual page an anonymous visitor sees, not a scaled-down preview.
    Deliberately never references any editor script — read-only markup,
    no editing surface for an anonymous visitor to reach. When a published
    template slug is provided, the page also includes the opt-in, first-party
    analytics consent UI and tracker."""
    if not isinstance(state, dict):
        return None
    document = state.get("document") or {}
    head = document.get("head") or {}
    body = document.get("body") or {}
    children = body.get("children") or []

    body_html = "".join(_render_node(child) for child in children)
    css = _render_styles(state.get("styles") or {})
    metas_html = "".join(f"<meta{_render_attributes(meta)}>" for meta in (head.get("metas") or []))
    title = escape(str(head.get("title") or title_fallback))
    doctype = escape(str(document.get("doctype") or "html"))
    html_attrs_html = _render_attributes(document.get("htmlAttributes") or {})
    body_attrs_html = _render_attributes(body.get("attributes") or {})
    analytics_head_html = ""
    analytics_body_html = ""
    if analytics_template_slug:
        safe_slug = escape(str(analytics_template_slug), quote=True)
        analytics_head_html = '<link rel="stylesheet" href="/static/analytics/public-tracker.css">'
        analytics_body_html = (
            f'<div id="analyticsConsent" data-template-slug="{safe_slug}"></div>'
            f'<script src="/static/analytics/public-tracker.js" '
            f'data-template-slug="{safe_slug}" defer></script>'
        )

    return (
        f"<!DOCTYPE {doctype}><html{html_attrs_html}><head>"
        '<meta charset="UTF-8">'
        f"{metas_html}<title>{title}</title>"
        '<link rel="stylesheet" href="/static/shared/tokens.css">'
        '<link rel="stylesheet" href="/static/editor/tailwind.css">'
        f"{analytics_head_html}"
        f"<style>{css}</style>"
        f"</head><body{body_attrs_html}>{body_html}{analytics_body_html}</body></html>"
    )
