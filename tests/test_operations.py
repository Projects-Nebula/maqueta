import pytest

from apps.ai_assistant.operations import OperationValidationError, validate_operations


def _ok(op):
    return validate_operations([op], max_operations=20)


def test_valid_operations_pass():
    assert _ok({"action": "set_text", "path": [0, 1], "value": "hola"})


def test_unknown_action_rejected():
    with pytest.raises(OperationValidationError):
        _ok({"action": "drop_database"})


def test_negative_path_rejected():
    with pytest.raises(OperationValidationError):
        _ok({"action": "set_text", "path": [0, -1], "value": "x"})


def test_non_integer_path_rejected():
    with pytest.raises(OperationValidationError):
        _ok({"action": "delete_node", "path": [0, "a"]})


def test_cyclic_move_rejected():
    with pytest.raises(OperationValidationError):
        _ok(
            {
                "action": "move_node",
                "source_path": [1],
                "target_path": [1, 0],
                "position": "inside",
            }
        )


def test_forbidden_tag_rejected():
    node = {"type": "element", "tag": "script", "children": []}
    with pytest.raises(OperationValidationError):
        _ok({"action": "add_node", "parent_path": [0], "index": 0, "node": node})


def test_event_handler_attribute_rejected():
    node = {"type": "element", "tag": "div", "attributes": {"onclick": "x()"}, "children": []}
    with pytest.raises(OperationValidationError):
        _ok({"action": "replace_node", "path": [0], "node": node})


def test_javascript_url_rejected():
    with pytest.raises(OperationValidationError):
        _ok(
            {
                "action": "set_attribute",
                "path": [0],
                "attribute": "href",
                "value": "javascript:alert(1)",
            }
        )


def test_disallowed_css_property_rejected():
    with pytest.raises(OperationValidationError):
        _ok(
            {
                "action": "set_css_declaration",
                "selector": ".x",
                "property": "behavior",
                "value": "url(x.htc)",
            }
        )


def test_too_many_operations_rejected():
    ops = [{"action": "set_text", "path": [0], "value": "x"}] * 21
    with pytest.raises(OperationValidationError):
        validate_operations(ops, max_operations=20)


def test_product_id_attribute_accepts_digit_string():
    assert _ok(
        {
            "action": "set_attribute",
            "path": [0],
            "attribute": "data-product-id",
            "value": "42",
        }
    )


def test_product_id_attribute_rejects_non_digit():
    with pytest.raises(OperationValidationError):
        _ok(
            {
                "action": "set_attribute",
                "path": [0],
                "attribute": "data-product-id",
                "value": "42; DROP TABLE products",
            }
        )


def test_iframe_with_youtube_embed_src_accepted():
    node = {
        "type": "element",
        "tag": "iframe",
        "attributes": {"src": "https://www.youtube.com/embed/kAoSM_p3G5U"},
        "children": [],
    }
    assert _ok({"action": "add_node", "parent_path": [0], "index": 0, "node": node})


def test_iframe_with_watch_url_rejected():
    node = {
        "type": "element",
        "tag": "iframe",
        "attributes": {"src": "https://www.youtube.com/watch?v=kAoSM_p3G5U"},
        "children": [],
    }
    with pytest.raises(OperationValidationError):
        _ok({"action": "add_node", "parent_path": [0], "index": 0, "node": node})


def test_iframe_with_arbitrary_src_rejected():
    node = {
        "type": "element",
        "tag": "iframe",
        "attributes": {"src": "https://evil.example.com/phish"},
        "children": [],
    }
    with pytest.raises(OperationValidationError):
        _ok({"action": "add_node", "parent_path": [0], "index": 0, "node": node})
