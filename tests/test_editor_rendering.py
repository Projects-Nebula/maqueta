from apps.editor.rendering import thumbnail_srcdoc


def _state(children=None, rules=None, variables=None, media_queries=None):
    return {
        "document": {"body": {"attributes": {}, "children": children or []}},
        "styles": {
            "variables": variables or {},
            "rules": rules or [],
            "mediaQueries": media_queries or [],
        },
    }


def test_none_state_returns_none():
    assert thumbnail_srcdoc(None) is None


def test_empty_body_returns_none():
    assert thumbnail_srcdoc(_state(children=[])) is None


def test_renders_element_and_text_nodes():
    state = _state(
        children=[
            {
                "type": "element",
                "tag": "h1",
                "attributes": {"class": ["title"]},
                "children": [{"type": "text", "value": "Hola"}],
            }
        ]
    )
    html = thumbnail_srcdoc(state)
    assert '<h1 class="title">Hola</h1>' in html


def test_escapes_text_and_attribute_values():
    state = _state(
        children=[
            {
                "type": "element",
                "tag": "p",
                "attributes": {"title": '"><script>alert(1)</script>'},
                "children": [{"type": "text", "value": "<script>alert(2)</script>"}],
            }
        ]
    )
    html = thumbnail_srcdoc(state)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_includes_style_rules_and_variables():
    state = _state(
        children=[{"type": "element", "tag": "div", "attributes": {}, "children": []}],
        rules=[{"selector": "div", "declarations": {"color": "red"}}],
        variables={"--accent": "#123456"},
    )
    html = thumbnail_srcdoc(state)
    assert "div { color: red }" in html
    assert "--accent: #123456" in html


def test_includes_media_query_rules():
    state = _state(
        children=[{"type": "element", "tag": "div", "attributes": {}, "children": []}],
        media_queries=[
            {
                "query": "(max-width: 640px)",
                "rules": [{"selector": "div", "declarations": {"font-size": "12px"}}],
            }
        ],
    )
    html = thumbnail_srcdoc(state)
    assert "@media (max-width: 640px) { div { font-size: 12px } }" in html
