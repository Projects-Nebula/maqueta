import copy

import pytest

from apps.ai_assistant.document_validation import DocumentValidationError, sanitize_document
from apps.ai_assistant.operations import OperationValidationError, validate_operations
from apps.editor.palettes import (
    PALETTE_PRESETS,
    PaletteValidationError,
    get_palette_preset,
    validate_palette_metadata,
    validate_palette_state,
)
from tests.test_document_validation import VALID_DOCUMENT


def test_catalog_presets_have_valid_metadata_and_four_hex_roles():
    for preset in PALETTE_PRESETS:
        metadata = {key: preset[key] for key in ("id", "name", "source")}
        assert validate_palette_metadata(metadata, variables=preset["variables"]) == metadata


def test_catalog_returns_defensive_copy():
    preset = get_palette_preset("ocean")
    preset["variables"]["--color-primary"] = "#000000"
    assert get_palette_preset("ocean")["variables"]["--color-primary"] == "#0f766e"


def test_legacy_state_without_palette_metadata_remains_valid():
    state = {"document": {}, "styles": {"variables": {"--color-primary": "#123456"}}}
    validate_palette_state(state)


@pytest.mark.parametrize(
    "palette",
    [
        {"id": "not safe", "name": "Paleta", "source": "custom"},
        {"id": "custom", "name": "", "source": "custom"},
        {"id": "custom", "name": "Paleta", "source": "unknown"},
    ],
)
def test_invalid_palette_metadata_is_rejected(palette):
    with pytest.raises(PaletteValidationError):
        validate_palette_metadata(palette)


def test_palette_metadata_requires_all_four_role_values():
    state = {
        "styles": {
            "palette": {"id": "custom", "name": "Mi paleta", "source": "custom"},
            "variables": {"--color-primary": "#123456"},
        }
    }
    with pytest.raises(PaletteValidationError):
        validate_palette_state(state)


def test_document_validation_rejects_css_expression_in_palette_role():
    document = copy.deepcopy(VALID_DOCUMENT)
    document["styles"]["palette"] = {
        "id": "custom",
        "name": "Mi paleta",
        "source": "custom",
    }
    document["styles"]["variables"] = {
        "--color-primary": "url(https://evil.example/x)",
        "--color-background": "#ffffff",
        "--color-text": "#111111",
        "--color-surface": "#ffffff",
    }
    with pytest.raises(DocumentValidationError):
        sanitize_document(document)


def test_style_variable_operation_is_limited_to_palette_roles_and_hex_values():
    validate_operations(
        [
            {
                "action": "set_style_variable",
                "name": "--color-primary",
                "value": "#123456",
            }
        ],
        max_operations=5,
    )
    with pytest.raises(OperationValidationError):
        validate_operations(
            [{"action": "set_style_variable", "name": "--font-primary", "value": "Arial"}],
            max_operations=5,
        )
    with pytest.raises(OperationValidationError):
        validate_operations(
            [{"action": "set_style_variable", "name": "--color-primary", "value": "#fff"}],
            max_operations=5,
        )
