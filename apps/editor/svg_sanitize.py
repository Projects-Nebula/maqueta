"""Sanitize untrusted SVG uploads by re-serializing a cleaned parse tree.

Mirrors the doctrine in ``image_processing.py``: an attacker-controlled
upload is never stored or served verbatim. Here that means parsing with
``defusedxml`` (XXE- and entity-expansion-safe), walking the tree to strip
anything that could execute script or reach outside the bundle's own
asset set, then re-serializing the survivors — the original bytes are
discarded once parsed.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, ParseError, register_namespace, tostring

import defusedxml.ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

# Re-serialize with the conventional prefixes instead of ElementTree's
# auto-generated "ns0:" so cleaned SVGs stay recognizable/diffable.
register_namespace("", "http://www.w3.org/2000/svg")
register_namespace("xlink", "http://www.w3.org/1999/xlink")

ASSET_URL_PREFIX = "/media/"

# Elements that can execute script, embed foreign (non-SVG) documents, or
# carry raw CSS (<style>'s text content is copied through verbatim by
# _clean_element with no CSS sanitization — e.g. @import/url() exfiltration
# — so the whole element is dropped rather than reopening a second CSS
# parser here).
FORBIDDEN_TAGS = {
    "script",
    "foreignobject",
    "animate",  # can retarget attributes (e.g. xlink:href) over time
    "animatetransform",
    "animatemotion",
    "set",
    "iframe",
    "object",
    "embed",
    "style",
}

# Matches apps/ai_assistant/sanitize.py's MAX_NODE_DEPTH guard — a
# well-formed but deeply nested SVG must fail closed with
# SvgSanitizationError, not an uncaught RecursionError from the recursive
# tree walk below.
MAX_ELEMENT_DEPTH = 40

# Attributes whose value is a URL/reference and therefore needs scheme
# checking, mirroring apps/ai_assistant/sanitize.py's URL_ATTRS.
URL_ATTRS = {"href", "xlink:href", "src"}


def _local_name(tag: str) -> str:
    """Strip an XML namespace URI from an ElementTree tag (`{ns}tag` -> `tag`)."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _is_safe_url_target(value: str, *, asset_url_prefix: str) -> bool:
    raw = value.strip()
    if not raw:
        return True
    if raw.startswith("#"):
        return True
    return raw.startswith(asset_url_prefix)


class SvgSanitizationError(ValueError):
    """Raised when untrusted SVG bytes can't be parsed or safely cleaned."""


def _clean_element(element: Element, *, asset_url_prefix: str, depth: int = 0) -> Element | None:
    """Return a cleaned copy of ``element``, or None if it must be dropped."""
    if depth > MAX_ELEMENT_DEPTH:
        raise SvgSanitizationError("SVG nesting exceeds the maximum allowed depth")

    tag = _local_name(element.tag).lower()
    if tag in FORBIDDEN_TAGS:
        return None

    cleaned = Element(element.tag, {})
    cleaned.text = element.text
    cleaned.tail = element.tail

    for name, value in element.attrib.items():
        attr_local = _local_name(name).lower()
        if attr_local.startswith("on"):
            continue
        if attr_local in ("style",):
            # No general inline style support for bundle SVGs in this PR —
            # dropping keeps the attack surface to the element/attribute
            # allowlist below rather than reopening a second CSS parser.
            continue
        if name.lower() in URL_ATTRS or attr_local in URL_ATTRS:
            if not _is_safe_url_target(value, asset_url_prefix=asset_url_prefix):
                continue
        cleaned.set(name, value)

    for child in element:
        cleaned_child = _clean_element(child, asset_url_prefix=asset_url_prefix, depth=depth + 1)
        if cleaned_child is not None:
            cleaned.append(cleaned_child)

    return cleaned


def sanitize_svg(data: bytes, *, asset_url_prefix: str = ASSET_URL_PREFIX) -> bytes:
    """Return re-serialized, safe SVG bytes.

    Forbidden elements/attributes (script, event handlers, style, unsafe
    URL targets, ...) are dropped SILENTLY — a successful return means the
    output is safe, not that it's unchanged from the input. Callers that
    need to tell the seller something was removed must diff the input
    against the output themselves; this function has no partial-failure
    signal beyond raising.

    Raises ``SvgSanitizationError`` if ``data`` isn't parseable XML,
    carries a DOCTYPE/external-entity declaration (XXE, billion-laughs),
    or nests deeper than ``MAX_ELEMENT_DEPTH``.
    """
    if not isinstance(data, bytes):
        raise SvgSanitizationError("SVG data must be bytes")

    try:
        root = DefusedET.fromstring(
            data,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except DefusedXmlException as exc:
        raise SvgSanitizationError(f"unsafe SVG (XXE/DTD): {exc}") from exc
    except ParseError as exc:
        raise SvgSanitizationError(f"invalid SVG: {exc}") from exc

    if _local_name(root.tag).lower() != "svg":
        raise SvgSanitizationError(f"not an SVG document: {root.tag}")

    cleaned_root = _clean_element(root, asset_url_prefix=asset_url_prefix)
    if cleaned_root is None:
        raise SvgSanitizationError("SVG root element rejected")

    return tostring(cleaned_root, encoding="utf-8")
