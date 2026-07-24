"""Tailwind utility-class allowlist — single source of truth.

Used both to validate AI/editor output (the same security role
`CSS_PROPERTY_ALLOWLIST` played before this refactor — see sanitize.py) and
to generate the safelist file that drives the Tailwind CLI build (see
`apps/editor/management/commands/generate_tailwind_safelist.py`). The
validator (`is_allowed_tailwind_class`) and the generator
(`iter_all_allowed_classes`) are derived from the same rule tables below by
construction — never hand-maintain two separate lists.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from apps.editor.palettes import PALETTE_VARIABLE_NAMES

from .sanitize import SanitizationError

CSS_VAR_RE = re.compile(r"^--[a-z0-9-]+$", re.IGNORECASE)

MAX_CLASSES_PER_NODE = 20

# Same brand-color variable names the global design panel
# (templates/editor/editor.html's "Diseño global" tab) actually writes into
# styles.variables — the only variable names the arbitrary-value bridge
# (`bg-[var(--x)]`) may reference. Keep in sync with that panel's fields.
KNOWN_VARIABLE_NAMES = frozenset(PALETTE_VARIABLE_NAMES)

SPACING_SCALE = {
    "0",
    "0.5",
    "1",
    "1.5",
    "2",
    "2.5",
    "3",
    "3.5",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "14",
    "16",
    "20",
    "24",
    "28",
    "32",
    "36",
    "40",
    "44",
    "48",
    "52",
    "56",
    "60",
    "64",
    "72",
    "80",
    "96",
    "px",
    "auto",
}
SIZING_SCALE = SPACING_SCALE | {
    "full",
    "screen",
    "min",
    "max",
    "fit",
    "1/2",
    "1/3",
    "2/3",
    "1/4",
    "2/4",
    "3/4",
    "1/5",
    "2/5",
    "3/5",
    "4/5",
}
# max-w-* (and, less commonly, w-*) also has this named container-width
# scale, independent of the numeric spacing scale — max-w-4xl is one of the
# most common Tailwind classes for a page container and was missing here
# until a real AI generation attempt got rejected for using it.
MAX_WIDTH_NAMED_SCALE = {
    "xs",
    "sm",
    "md",
    "lg",
    "xl",
    "2xl",
    "3xl",
    "4xl",
    "5xl",
    "6xl",
    "7xl",
    "full",
    "min",
    "max",
    "fit",
    "prose",
    "none",
}
GRID_SPAN_SCALE = {str(n) for n in range(1, 13)} | {"full", "auto"}
FONT_SIZE_SCALE = {"xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl", "6xl", "7xl"}
FONT_WEIGHT_SCALE = {
    "thin",
    "extralight",
    "light",
    "normal",
    "medium",
    "semibold",
    "bold",
    "extrabold",
    "black",
}
LEADING_SCALE = {"none", "tight", "snug", "normal", "relaxed", "loose"} | {
    str(n) for n in (3, 4, 5, 6, 7, 8, 9, 10)
}
TRACKING_SCALE = {"tighter", "tight", "normal", "wide", "wider", "widest"}
RADIUS_SCALE = {"none", "sm", "md", "lg", "xl", "2xl", "3xl", "full"}
SHADOW_SCALE = {"sm", "md", "lg", "xl", "2xl", "inner", "none"}
OPACITY_SCALE = {str(n) for n in range(0, 101, 5)}
BLUR_SCALE = {"none", "sm", "md", "lg", "xl", "2xl", "3xl"}
DURATION_SCALE = {"75", "100", "150", "200", "300", "500", "700", "1000"}
Z_SCALE = {"0", "10", "20", "30", "40", "50", "auto"}
BORDER_WIDTH_SCALE = {"0", "2", "4", "8", ""}  # "" -> bare "border"

TAILWIND_COLOR_NAMES = {
    "slate",
    "gray",
    "zinc",
    "neutral",
    "stone",
    "red",
    "orange",
    "amber",
    "yellow",
    "lime",
    "green",
    "emerald",
    "teal",
    "cyan",
    "sky",
    "blue",
    "indigo",
    "violet",
    "purple",
    "fuchsia",
    "pink",
    "rose",
}
TAILWIND_SHADE_SCALE = {"50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"}
BARE_COLOR_NAMES = {"white", "black", "transparent", "current"}

COLOR_PREFIXES = {"bg", "text", "border", "outline", "decoration"}

# prefix -> allowed value scale
UTILITY_FAMILIES: dict[str, set[str]] = {
    "p": SPACING_SCALE,
    "px": SPACING_SCALE,
    "py": SPACING_SCALE,
    "pt": SPACING_SCALE,
    "pr": SPACING_SCALE,
    "pb": SPACING_SCALE,
    "pl": SPACING_SCALE,
    "m": SPACING_SCALE,
    "mx": SPACING_SCALE,
    "my": SPACING_SCALE,
    "mt": SPACING_SCALE,
    "mr": SPACING_SCALE,
    "mb": SPACING_SCALE,
    "ml": SPACING_SCALE,
    "gap": SPACING_SCALE,
    "gap-x": SPACING_SCALE,
    "gap-y": SPACING_SCALE,
    "space-x": SPACING_SCALE,
    "space-y": SPACING_SCALE,
    "w": SIZING_SCALE,
    "h": SIZING_SCALE,
    "min-w": SIZING_SCALE,
    "max-w": SIZING_SCALE | MAX_WIDTH_NAMED_SCALE,
    "min-h": SIZING_SCALE,
    "max-h": SIZING_SCALE,
    "inset": SPACING_SCALE,
    "top": SPACING_SCALE,
    "right": SPACING_SCALE,
    "bottom": SPACING_SCALE,
    "left": SPACING_SCALE,
    "z": Z_SCALE,
    "text": FONT_SIZE_SCALE,  # font-size form; color form handled separately
    "font": FONT_WEIGHT_SCALE,
    "leading": LEADING_SCALE,
    "tracking": TRACKING_SCALE,
    "rounded": RADIUS_SCALE,
    "shadow": SHADOW_SCALE,
    "opacity": OPACITY_SCALE,
    "blur": BLUR_SCALE,
    "backdrop-blur": BLUR_SCALE,
    "duration": DURATION_SCALE,
    "scale": {"0", "50", "75", "90", "95", "100", "105", "110", "125", "150"},
    "rotate": {"0", "1", "2", "3", "6", "12", "45", "90", "180"},
    "grid-cols": GRID_SPAN_SCALE,
    "grid-rows": GRID_SPAN_SCALE,
    "col-span": GRID_SPAN_SCALE,
    "row-span": GRID_SPAN_SCALE,
    "order": {str(n) for n in range(1, 13)} | {"first", "last", "none"},
    "aspect": {"auto", "square", "video"},
    "line-clamp": {"1", "2", "3", "4", "5", "6", "none"},
}

STANDALONE_TOKENS = {
    "flex",
    "inline-flex",
    "grid",
    "inline-grid",
    "block",
    "inline-block",
    "inline",
    "hidden",
    "contents",
    "flex-row",
    "flex-row-reverse",
    "flex-col",
    "flex-col-reverse",
    "flex-wrap",
    "flex-nowrap",
    "flex-wrap-reverse",
    "flex-1",
    "flex-auto",
    "flex-initial",
    "flex-none",
    "grow",
    "grow-0",
    "shrink",
    "shrink-0",
    "justify-start",
    "justify-end",
    "justify-center",
    "justify-between",
    "justify-around",
    "justify-evenly",
    "items-start",
    "items-end",
    "items-center",
    "items-baseline",
    "items-stretch",
    "content-start",
    "content-end",
    "content-center",
    "content-between",
    "content-around",
    "content-evenly",
    "self-auto",
    "self-start",
    "self-end",
    "self-center",
    "self-stretch",
    "relative",
    "absolute",
    "fixed",
    "sticky",
    "static",
    "italic",
    "not-italic",
    "underline",
    "line-through",
    "no-underline",
    "uppercase",
    "lowercase",
    "capitalize",
    "normal-case",
    "truncate",
    "text-ellipsis",
    "text-clip",
    "text-left",
    "text-center",
    "text-right",
    "text-justify",
    "whitespace-normal",
    "whitespace-nowrap",
    "whitespace-pre",
    "break-normal",
    "break-words",
    "break-all",
    "align-baseline",
    "align-top",
    "align-middle",
    "align-bottom",
    "box-border",
    "box-content",
    "overflow-auto",
    "overflow-hidden",
    "overflow-visible",
    "overflow-scroll",
    "overflow-x-auto",
    "overflow-x-hidden",
    "overflow-y-auto",
    "overflow-y-hidden",
    "scroll-auto",
    "scroll-smooth",
    "cursor-auto",
    "cursor-default",
    "cursor-pointer",
    "cursor-not-allowed",
    "pointer-events-none",
    "pointer-events-auto",
    "select-none",
    "select-text",
    "select-all",
    "transition",
    "transition-none",
    "transition-colors",
    "transition-opacity",
    "transition-transform",
    "transition-all",
    "ease-linear",
    "ease-in",
    "ease-out",
    "ease-in-out",
    "object-contain",
    "object-cover",
    "object-fill",
    "object-none",
    "object-scale-down",
    "border",
    "border-t",
    "border-r",
    "border-b",
    "border-l",
    "rounded-full",
    "float-left",
    "float-right",
    "float-none",
    "clear-left",
    "clear-right",
    "clear-both",
    "clear-none",
    "backdrop-blur",
}

RESPONSIVE_PREFIXES = {"sm", "md", "lg", "xl", "2xl"}
STATE_PREFIXES = {"hover", "focus", "focus-visible", "active", "disabled"}

_COLOR_TOKEN_RE = re.compile(
    r"^("
    + "|".join(COLOR_PREFIXES)
    + r")-("
    + "|".join(TAILWIND_COLOR_NAMES)
    + r")-("
    + "|".join(TAILWIND_SHADE_SCALE)
    + r")$"
)
_BARE_COLOR_TOKEN_RE = re.compile(
    r"^(" + "|".join(COLOR_PREFIXES) + r")-(" + "|".join(BARE_COLOR_NAMES) + r")$"
)
_ARBITRARY_VAR_RE = re.compile(r"^(" + "|".join(COLOR_PREFIXES) + r")-\[var\((--[a-z0-9-]+)\)\]$")


def _split_prefixes(token: str) -> str | None:
    """Strip at most one responsive prefix and/or one state prefix. Return
    the remaining unprefixed utility, or None if the token is malformed
    (more than one of either prefix kind, or nothing left after stripping)."""
    parts = token.split(":")
    if len(parts) > 3:
        return None
    seen_responsive = False
    seen_state = False
    for part in parts[:-1]:
        if part in RESPONSIVE_PREFIXES and not seen_responsive:
            seen_responsive = True
        elif part in STATE_PREFIXES and not seen_state:
            seen_state = True
        else:
            return None
    remainder = parts[-1]
    return remainder or None


def is_allowed_tailwind_class(token: str) -> bool:
    if not isinstance(token, str) or not token:
        return False
    remainder = _split_prefixes(token)
    if not remainder:
        return False

    if remainder in STANDALONE_TOKENS:
        return True

    if _COLOR_TOKEN_RE.match(remainder) or _BARE_COLOR_TOKEN_RE.match(remainder):
        return True

    var_match = _ARBITRARY_VAR_RE.match(remainder)
    if var_match and var_match.group(2) in KNOWN_VARIABLE_NAMES:
        return True

    for prefix in sorted(UTILITY_FAMILIES, key=len, reverse=True):
        if remainder == prefix or remainder.startswith(prefix + "-"):
            value = remainder[len(prefix) + 1 :] if remainder != prefix else ""
            if value in UTILITY_FAMILIES[prefix]:
                return True

    return False


def iter_all_allowed_classes() -> Iterator[str]:
    """Every literal class string the rules above allow — feeds the
    Tailwind build's safelist (see the generate_tailwind_safelist
    management command). Deliberately excludes the CSS-variable
    arbitrary-value form (that's validated dynamically, not safelisted —
    see REFACTOR.md Section 3.3)."""
    prefixes: list[str] = [""]
    for resp in RESPONSIVE_PREFIXES:
        prefixes.append(f"{resp}:")
    for state in STATE_PREFIXES:
        prefixes.append(f"{state}:")

    bases: set[str] = set(STANDALONE_TOKENS)
    for prefix, scale in UTILITY_FAMILIES.items():
        for value in scale:
            bases.add(f"{prefix}-{value}" if value else prefix)
    for color in TAILWIND_COLOR_NAMES:
        for shade in TAILWIND_SHADE_SCALE:
            for cprefix in COLOR_PREFIXES:
                bases.add(f"{cprefix}-{color}-{shade}")
    for color in BARE_COLOR_NAMES:
        for cprefix in COLOR_PREFIXES:
            bases.add(f"{cprefix}-{color}")

    for prefix in prefixes:
        for base in bases:
            yield f"{prefix}{base}"


def check_class_list(value) -> None:
    """value is whatever came from a node's `attributes.class` — str or
    list of str, per operations.py's `_validate_class_or_text`."""
    if isinstance(value, list):
        if not all(isinstance(v, str) for v in value):
            raise SanitizationError("class list must be strings")
        tokens = value
    elif isinstance(value, str):
        tokens = value.split()
    else:
        raise SanitizationError("class value must be a string or list")
    if len(tokens) > MAX_CLASSES_PER_NODE:
        raise SanitizationError("too many classes on one element")
    for token in tokens:
        if not is_allowed_tailwind_class(token):
            raise SanitizationError(f"disallowed Tailwind class: {token}")


def normalize_context_class_list(value):
    """Keep only current Tailwind classes in AI-only node context.

    Saved pages created before the Tailwind migration may contain semantic
    classes such as ``site-header``. They are useful to the renderer, but
    they are not valid classes for an AI-generated ``set_attribute`` value.
    Context normalization removes those legacy tokens before the model sees
    the node; ``check_class_list`` remains strict for every generated node or
    operation.
    """
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise SanitizationError("class list must be strings")
        tokens = value
        as_list = True
    elif isinstance(value, str):
        tokens = value.split()
        as_list = False
    else:
        raise SanitizationError("class value must be a string or list")

    if len(tokens) > MAX_CLASSES_PER_NODE:
        raise SanitizationError("too many classes on one element")

    normalized = [token for token in tokens if is_allowed_tailwind_class(token)]
    return normalized if as_list else " ".join(normalized)
