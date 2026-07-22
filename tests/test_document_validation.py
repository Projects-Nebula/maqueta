import copy

import pytest

from apps.ai_assistant.document_validation import DocumentValidationError, sanitize_document

VALID_DOCUMENT = {
    "schemaVersion": "2.0",
    "settings": {
        "strict": True,
        "escapeText": True,
        "allowRawHtml": False,
        "allowInlineScripts": False,
        "requireImageAlt": True,
        "requireUniqueIds": True,
    },
    "document": {
        "doctype": "html",
        "htmlAttributes": {"lang": "es", "dir": "ltr"},
        "head": {
            "title": "Mi negocio",
            "metas": [{"charset": "UTF-8"}],
            "links": [],
            "scripts": [],
        },
        "body": {
            "attributes": {"class": ["page"]},
            "children": [
                {
                    "type": "element",
                    "tag": "h1",
                    "attributes": {},
                    "children": [{"type": "text", "value": "Bienvenido"}],
                }
            ],
        },
    },
    "styles": {
        "variables": {"--color-primary": "#5b5ce2"},
        "rules": [{"selector": "h1", "declarations": {"color": "var(--color-primary)"}}],
        "keyframes": [],
    },
    "components": {},
    "assets": {},
}


def _doc(**overrides):
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc.update(overrides)
    return doc


def test_valid_document_passes():
    sanitize_document(VALID_DOCUMENT)


def test_scripts_must_be_empty():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["document"]["head"]["scripts"] = [{"src": "evil.js"}]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_links_must_be_empty():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["document"]["head"]["links"] = [{"rel": "stylesheet", "href": "https://evil.example/x.css"}]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_allow_raw_html_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["settings"]["allowRawHtml"] = True
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_allow_inline_scripts_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["settings"]["allowInlineScripts"] = True
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_forbidden_tag_in_body_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["document"]["body"]["children"].append(
        {"type": "element", "tag": "script", "attributes": {}, "children": []}
    )
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_disallowed_css_property_in_rules_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    bad_rule = {"selector": "body", "declarations": {"behavior": "url(evil.htc)"}}
    doc["styles"]["rules"].append(bad_rule)
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_recently_expanded_css_properties_are_allowed():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["rules"].append(
        {
            "selector": ".card",
            "declarations": {
                "background-position": "center",
                "background-size": "cover",
                "background-repeat": "no-repeat",
                "inset": "0",
                "filter": "blur(4px)",
                "outline-offset": "2px",
                "text-overflow": "ellipsis",
                "-webkit-line-clamp": "2",
                "grid-column": "span 2",
                "flex-basis": "50%",
                "order": "1",
                "float": "left",
            },
        }
    )
    sanitize_document(doc)


def test_unsafe_css_selector_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    bad_rule = {"selector": "h1{}</style><script>", "declarations": {"color": "red"}}
    doc["styles"]["rules"].append(bad_rule)
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_keyframes_must_be_empty():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["keyframes"] = [{"name": "spin", "steps": []}]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_components_must_be_empty():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["components"] = {"card": {}}
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_valid_asset_entry_passes():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["assets"] = {
        "logo": {"url": "/media/wizard-uploads/2024/01/logo.jpg", "width": 200, "height": 100}
    }
    sanitize_document(doc)


def test_asset_external_url_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["assets"] = {"logo": {"url": "https://example.com/logo.png", "width": 200, "height": 100}}
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_asset_dangling_keys_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["assets"] = {
        "logo": {
            "url": "/media/wizard-uploads/2024/01/logo.jpg",
            "width": 200,
            "height": 100,
            "extra": "nope",
        }
    }
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_asset_invalid_dimensions_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["assets"] = {
        "logo": {"url": "/media/wizard-uploads/2024/01/logo.jpg", "width": 0, "height": 100}
    }
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_too_many_assets_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["assets"] = {
        f"img{i}": {"url": "/media/x.jpg", "width": 10, "height": 10} for i in range(21)
    }
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_unexpected_top_level_key_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["extra"] = "nope"
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_invalid_lang_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["document"]["htmlAttributes"]["lang"] = "<script>"
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_too_many_style_variables_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["variables"] = {f"--v{i}": "#fff" for i in range(101)}
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_dangling_keys_on_document_rejected():
    # Reproduces a real json-repair failure mode: a truncated/malformed
    # response gets its syntax "fixed" by closing body.children early, and
    # what should have been the next section ends up as stray
    # type/tag/attributes/children keys directly on document.document
    # instead — silently dropping content rather than raising a parse error.
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["document"]["type"] = "element"
    doc["document"]["tag"] = "section"
    doc["document"]["attributes"] = {"class": ["hero"]}
    doc["document"]["children"] = []
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_dangling_keys_on_body_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["document"]["body"]["type"] = "element"
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_dangling_keys_on_style_rule_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["rules"][0]["extra"] = "nope"
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_valid_media_query_passes():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["mediaQueries"] = [
        {
            "query": "(max-width: 640px)",
            "rules": [{"selector": "h1", "declarations": {"font-size": "20px"}}],
        }
    ]
    sanitize_document(doc)


def test_media_query_injection_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["mediaQueries"] = [{"query": "screen) {} body{}</style><script>", "rules": []}]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_media_query_dangling_keys_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["mediaQueries"] = [{"query": "(max-width: 640px)", "rules": [], "extra": "nope"}]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_media_query_nested_rule_disallowed_property_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["mediaQueries"] = [
        {
            "query": "(max-width: 640px)",
            "rules": [{"selector": "body", "declarations": {"behavior": "url(evil.htc)"}}],
        }
    ]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)


def test_too_many_media_queries_rejected():
    doc = copy.deepcopy(VALID_DOCUMENT)
    doc["styles"]["mediaQueries"] = [
        {"query": f"(min-width: {i}px)", "rules": []} for i in range(11)
    ]
    with pytest.raises(DocumentValidationError):
        sanitize_document(doc)
