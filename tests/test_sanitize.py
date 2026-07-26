import pytest

from apps.ai_assistant.sanitize import (
    SanitizationError,
    check_css_declaration,
    check_css_variable,
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
