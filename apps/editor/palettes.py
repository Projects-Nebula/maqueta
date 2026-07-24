"""Canonical palette presets and validation helpers.

The editor stores the active colors in ``styles.variables``.  ``styles.palette``
only describes where those values came from, so renderers never need a second
color source and legacy documents remain valid when the metadata is absent.
"""

from __future__ import annotations

import copy
import re

PALETTE_ROLES = (
    {"id": "primary", "variable": "--color-primary", "label": "Principal"},
    {"id": "background", "variable": "--color-background", "label": "Fondo"},
    {"id": "text", "variable": "--color-text", "label": "Texto"},
    {"id": "surface", "variable": "--color-surface", "label": "Superficie"},
)
PALETTE_VARIABLE_NAMES = tuple(role["variable"] for role in PALETTE_ROLES)
PALETTE_SOURCE_VALUES = frozenset({"preset", "custom", "ai"})
PALETTE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Generic, descriptive presets.  They intentionally do not copy a third
# party's logo, trademark, font, or full visual identity.
PALETTE_PRESETS = (
    {
        "id": "ocean",
        "name": "Océano",
        "description": "Azules serenos para productos claros y confiables.",
        "source": "preset",
        "variables": {
            "--color-primary": "#0f766e",
            "--color-background": "#f0fdfa",
            "--color-text": "#134e4a",
            "--color-surface": "#ffffff",
        },
    },
    {
        "id": "forest",
        "name": "Bosque",
        "description": "Verdes naturales con una base fresca y luminosa.",
        "source": "preset",
        "variables": {
            "--color-primary": "#166534",
            "--color-background": "#f0fdf4",
            "--color-text": "#14532d",
            "--color-surface": "#ffffff",
        },
    },
    {
        "id": "sunset",
        "name": "Atardecer",
        "description": "Naranjas cálidos para marcas expresivas y cercanas.",
        "source": "preset",
        "variables": {
            "--color-primary": "#c2410c",
            "--color-background": "#fff7ed",
            "--color-text": "#431407",
            "--color-surface": "#ffffff",
        },
    },
    {
        "id": "neutral",
        "name": "Neutro",
        "description": "Grises equilibrados para una presentación profesional.",
        "source": "preset",
        "variables": {
            "--color-primary": "#475569",
            "--color-background": "#f8fafc",
            "--color-text": "#0f172a",
            "--color-surface": "#ffffff",
        },
    },
    {
        "id": "high-contrast",
        "name": "Alto contraste",
        "description": "Contraste marcado para priorizar legibilidad y acción.",
        "source": "preset",
        "variables": {
            "--color-primary": "#facc15",
            "--color-background": "#050505",
            "--color-text": "#ffffff",
            "--color-surface": "#111111",
        },
    },
)

_PRESETS_BY_ID = {preset["id"]: preset for preset in PALETTE_PRESETS}


class PaletteValidationError(ValueError):
    """Raised when palette metadata or role values violate the contract."""


def _check_safe_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 80:
        raise PaletteValidationError(
            "palette.name must be a non-empty string of at most 80 characters"
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in cleaned):
        raise PaletteValidationError("palette.name contains control characters")
    return cleaned


def validate_palette_variables(variables, *, require_all: bool = False) -> dict:
    """Validate the semantic color roles without rejecting other style tokens."""

    if not isinstance(variables, dict):
        raise PaletteValidationError("styles.variables must be an object")
    validated = {}
    for variable in PALETTE_VARIABLE_NAMES:
        if variable not in variables:
            if require_all:
                raise PaletteValidationError(f"missing palette variable: {variable}")
            continue
        value = variables[variable]
        if not isinstance(value, str) or not HEX_COLOR_RE.fullmatch(value):
            raise PaletteValidationError(f"{variable} must be a six-digit hex color")
        validated[variable] = value
    return validated


def validate_palette_metadata(palette, *, variables=None) -> dict:
    """Validate and return a normalized copy of ``styles.palette``."""

    if not isinstance(palette, dict):
        raise PaletteValidationError("styles.palette must be an object")
    if set(palette) != {"id", "name", "source"}:
        raise PaletteValidationError("styles.palette must contain only id, name and source")

    palette_id = palette.get("id")
    if (
        not isinstance(palette_id, str)
        or len(palette_id) > 64
        or not PALETTE_ID_RE.fullmatch(palette_id)
    ):
        raise PaletteValidationError("palette.id must be a safe slug of at most 64 characters")
    name = palette.get("name")
    if not isinstance(name, str):
        raise PaletteValidationError("palette.name must be a string")
    name = _check_safe_name(name)
    source = palette.get("source")
    if source not in PALETTE_SOURCE_VALUES:
        raise PaletteValidationError("palette.source must be preset, custom or ai")

    normalized = {"id": palette_id, "name": name, "source": source}
    if variables is not None:
        role_values = validate_palette_variables(variables, require_all=True)
        if source == "preset":
            preset = _PRESETS_BY_ID.get(palette_id)
            if preset is None:
                raise PaletteValidationError(f"unknown palette preset: {palette_id}")
            if role_values != preset["variables"]:
                raise PaletteValidationError("preset palette variables do not match the catalog")
    return normalized


def validate_palette_state(state) -> None:
    """Validate palette data embedded in an editor state.

    A missing palette is deliberately accepted for backwards compatibility.
    The full document validator applies the same rule to AI-generated pages.
    """

    if not isinstance(state, dict):
        raise PaletteValidationError("state must be an object")
    styles = state.get("styles")
    if styles is None:
        return
    if not isinstance(styles, dict):
        raise PaletteValidationError("styles must be an object")
    palette = styles.get("palette")
    if palette is None:
        return
    validate_palette_metadata(palette, variables=styles.get("variables"))


def get_palette_preset(palette_id: str | None) -> dict | None:
    """Return a defensive copy of a catalog preset, if it exists."""

    preset = _PRESETS_BY_ID.get(palette_id)
    return copy.deepcopy(preset) if preset else None


def user_palette_for_client(user_palette) -> dict:
    """Serialize an owner-scoped ``UserPalette`` for editor/wizard clients.

    The model is deliberately duck-typed here so this canonical palette
    module does not import Django models. Invalid persisted data fails closed
    before it can be rendered or sent to the wizard.
    """

    variables = validate_palette_variables(user_palette.variables, require_all=True)
    metadata = validate_palette_metadata(
        {"id": user_palette.slug, "name": user_palette.name, "source": "custom"},
        variables=variables,
    )
    return {
        **metadata,
        "description": "Paleta guardada por vos para reutilizarla en otros templates.",
        "variables": copy.deepcopy(variables),
        "user_palette_id": user_palette.pk,
    }


def palette_catalog_for_client(user_palettes=()) -> dict:
    """Return the single palette catalog consumed by editor and wizard JS."""

    return {
        "roles": copy.deepcopy(PALETTE_ROLES),
        "presets": copy.deepcopy(PALETTE_PRESETS),
        "user_palettes": [user_palette_for_client(palette) for palette in user_palettes],
    }
