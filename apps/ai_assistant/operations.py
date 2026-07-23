"""Validation of the structured operations the AI is allowed to emit.

The AI never returns free HTML. It returns a list of operations, each of which
is validated here before it can reach the browser. Anything that fails is
rejected outright — the frontend applies only vetted operations.
"""

from __future__ import annotations

from .sanitize import (
    URL_ATTRS,
    SanitizationError,
    check_attribute_name,
    check_css_declaration,
    check_css_variable,
    check_url_value,
    sanitize_node,
)
from .tailwind_classes import check_class_list

POSITIONS = {"before", "after", "inside"}

ALLOWED_ACTIONS = {
    "set_text",
    "set_attribute",
    "remove_attribute",
    "set_style_variable",
    "set_css_declaration",
    "remove_css_declaration",
    "add_node",
    "replace_node",
    "duplicate_node",
    "delete_node",
    "move_node",
    "add_section",
}


class OperationValidationError(ValueError):
    """Raised when an AI operation is malformed or unsafe."""


def _require(condition, message):
    if not condition:
        raise OperationValidationError(message)


def _valid_path(value, field="path"):
    _require(isinstance(value, list), f"{field} must be a list")
    for item in value:
        _require(
            isinstance(item, int) and not isinstance(item, bool) and item >= 0,
            f"{field} must contain non-negative integers",
        )
    return value


def _is_prefix(prefix, path):
    return len(prefix) <= len(path) and all(a == b for a, b in zip(prefix, path))


def _validate_class_or_text(attribute, value):
    if attribute == "class":
        if isinstance(value, list):
            _require(all(isinstance(v, str) for v in value), "class list must be strings")
        else:
            _require(isinstance(value, str), "class value must be a string or list")
        try:
            check_class_list(value)
        except SanitizationError as exc:
            raise OperationValidationError(str(exc)) from exc
    else:
        _require(isinstance(value, str), f"{attribute} value must be a string")
        if attribute in URL_ATTRS:
            check_url_value(value)


def _validate_one(op):
    _require(isinstance(op, dict), "operation must be an object")
    action = op.get("action")
    _require(action in ALLOWED_ACTIONS, f"unknown action: {action}")

    if action == "set_text":
        _valid_path(op.get("path"))
        _require(isinstance(op.get("value"), str), "set_text value must be a string")

    elif action == "set_attribute":
        _valid_path(op.get("path"))
        attribute = op.get("attribute")
        _require(isinstance(attribute, str) and attribute, "attribute name required")
        check_attribute_name(attribute)
        _require(attribute.lower() != "style", "style attribute not allowed")
        _validate_class_or_text(attribute, op.get("value"))

    elif action == "remove_attribute":
        _valid_path(op.get("path"))
        attribute = op.get("attribute")
        _require(isinstance(attribute, str) and attribute, "attribute name required")
        check_attribute_name(attribute)

    elif action == "set_style_variable":
        check_css_variable(op.get("name"), op.get("value"))

    elif action == "set_css_declaration":
        _require(isinstance(op.get("selector"), str) and op["selector"], "selector required")
        prop = op.get("property")
        value = op.get("value")
        _require(isinstance(prop, str) and isinstance(value, str), "property/value required")
        check_css_declaration(prop, value)

    elif action == "remove_css_declaration":
        _require(isinstance(op.get("selector"), str) and op["selector"], "selector required")
        _require(isinstance(op.get("property"), str) and op["property"], "property required")

    elif action == "add_node":
        _valid_path(op.get("parent_path"), "parent_path")
        index = op.get("index")
        _require(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0,
            "index must be a non-negative integer",
        )
        sanitize_node(op.get("node"))

    elif action == "add_section":
        # A section is added at the body root by default.
        parent_path = op.get("parent_path", [])
        _valid_path(parent_path, "parent_path")
        index = op.get("index", 0)
        _require(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0,
            "index must be a non-negative integer",
        )
        sanitize_node(op.get("node"))

    elif action == "replace_node":
        _valid_path(op.get("path"))
        sanitize_node(op.get("node"))

    elif action == "duplicate_node":
        _valid_path(op.get("path"))

    elif action == "delete_node":
        _valid_path(op.get("path"))

    elif action == "move_node":
        source = _valid_path(op.get("source_path"), "source_path")
        target = _valid_path(op.get("target_path"), "target_path")
        position = op.get("position")
        _require(position in POSITIONS, f"invalid position: {position}")
        # A node can never be moved inside itself or its own subtree.
        _require(not _is_prefix(source, target), "cannot move a node into itself")


def validate_operations(operations, *, max_operations):
    """Validate a list of operations. Return it unchanged or raise.

    Raising keeps the contract simple: the caller rejects the whole AI
    response rather than silently applying a partial, possibly-inconsistent
    set of edits.
    """
    if not isinstance(operations, list):
        raise OperationValidationError("operations must be a list")
    if len(operations) == 0:
        raise OperationValidationError("no operations returned")
    if len(operations) > max_operations:
        raise OperationValidationError(f"too many operations: {len(operations)} > {max_operations}")
    try:
        for op in operations:
            _validate_one(op)
    except SanitizationError as exc:
        raise OperationValidationError(str(exc)) from exc
    return operations
