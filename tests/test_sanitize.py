import pytest

from apps.ai_assistant.sanitize import (
    SanitizationError,
    check_attributes,
    check_css_declaration,
    check_css_variable,
    check_style_attribute_value,
    sanitize_node,
)


def test_check_css_declaration_accepts_normal_value():
    check_css_declaration("color", "#ff0000")


@pytest.mark.parametrize(
    "value",
    [
        "red; } </style><script>alert(1)</script> {",
        "red } .x{color:red",
        "red</style>",
        "expression(alert(1))",
        "javascript:alert(1)",
    ],
)
def test_check_css_declaration_rejects_style_breakout(value):
    with pytest.raises(SanitizationError):
        check_css_declaration("color", value)


def test_check_css_variable_accepts_normal_value():
    check_css_variable("--color-primary", "#123456")


def test_check_css_variable_rejects_style_breakout():
    with pytest.raises(SanitizationError):
        check_css_variable("--color-primary", "red; } </style><script>alert(1)</script> {")


# --- allow_style regression lock (task 1.1/1.2) ----------------------------


def test_check_attributes_default_rejects_style():
    with pytest.raises(SanitizationError):
        check_attributes({"style": "color: red"})


def test_check_attributes_explicit_false_rejects_style():
    with pytest.raises(SanitizationError):
        check_attributes({"style": "color: red"}, allow_style=False)


def test_sanitize_node_default_rejects_style_attribute():
    node = {
        "type": "element",
        "tag": "div",
        "attributes": {"style": "color: red"},
        "children": [],
    }
    with pytest.raises(SanitizationError):
        sanitize_node(node)


def test_sanitize_node_default_rejects_style_on_nested_child():
    node = {
        "type": "element",
        "tag": "div",
        "attributes": {},
        "children": [
            {
                "type": "element",
                "tag": "span",
                "attributes": {"style": "color: red"},
                "children": [],
            }
        ],
    }
    with pytest.raises(SanitizationError):
        sanitize_node(node)


def test_check_attributes_allow_style_true_accepts_valid_style():
    # Opt-in path: valid declarations are accepted, no exception.
    check_attributes({"style": "color: red"}, allow_style=True)


def test_check_attributes_allow_style_true_still_rejects_unsafe_style():
    with pytest.raises(SanitizationError):
        check_attributes({"style": "background: url(javascript:alert(1))"}, allow_style=True)


# --- CSS_VALUE_FORBIDDEN protocol-relative url() bugfix (task 1.3/1.4) -----


@pytest.mark.parametrize(
    "value",
    [
        "background: url(//evil.com/x.png)",
        "background-image: url('//evil.com/x.png')",
    ],
)
def test_check_css_declaration_rejects_protocol_relative_url(value):
    prop, _, val = value.partition(":")
    with pytest.raises(SanitizationError):
        check_css_declaration(prop.strip(), val.strip())


@pytest.mark.parametrize(
    "value",
    [
        "url(#fragment)",
        "url(/local/path.png)",
        "url(data:image/png;base64,aGVsbG8=)",
    ],
)
def test_check_css_declaration_still_accepts_legitimate_urls(value):
    check_css_declaration("background-image", value)


@pytest.mark.parametrize(
    "value",
    [
        r"url(/\/evil.com/x.png)",
        r"url(/\2f evil.com/x.png)",
    ],
)
def test_check_css_declaration_rejects_escape_obfuscated_protocol_relative_url(value):
    """A CSS backslash escape (`\\/` or the hex form `\\2f `) decodes to a
    literal `/` at parse time, turning a value that LOOKS like a safe
    single-slash path into a protocol-relative external URL. Regression
    for a bypass the url() bugfix (task 1.3/1.4) initially missed because
    it only checked the raw, non-unescaped value."""
    with pytest.raises(SanitizationError):
        check_css_declaration("background-image", value)


# --- check_style_attribute_value (task 1.5/1.6) ----------------------------


@pytest.mark.parametrize(
    "value",
    [
        "width: expression(alert(1))",
        "background: javascript:alert(1)",
        "background: @import url(evil.css)",
        "background: url(//evil.com/x.png)",
        "background: url(https://evil.com/x.png)",
        "background: url(data:image/png;base64,aGVsbG8=)",
        "content: '<script>alert(1)</script>'",
        r"background: \6a avascript:alert(1)",
        "made-up-property: red",
    ],
)
def test_check_style_attribute_value_drops_unsafe_declarations(value):
    result = check_style_attribute_value(value)
    assert result == ""


def test_check_style_attribute_value_keeps_valid_bundle_local_url():
    result = check_style_attribute_value("background-image: url(/media/x.jpg)")
    assert "url(/media/x.jpg)" in result


def test_check_style_attribute_value_rejects_url_outside_asset_prefix():
    result = check_style_attribute_value(
        "background-image: url(/other/x.jpg)", asset_url_prefix="/media/"
    )
    assert result == ""


def test_check_style_attribute_value_mixed_declarations_keeps_only_safe_ones():
    value = "color: red; width: expression(alert(1)); font-weight: bold"
    result = check_style_attribute_value(value)
    assert "color: red" in result
    assert "font-weight: bold" in result
    assert "expression" not in result
