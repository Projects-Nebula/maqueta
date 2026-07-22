"""JSON schema advertised to the model for structured output.

The hard security enforcement lives in ``operations.validate_operations``;
this schema shapes the model's output so it returns the right envelope.
"""

EDITOR_CLARIFY_JSON_SCHEMA = {
    "type": "object",
    "required": ["instruction"],
    "properties": {
        "instruction": {"type": "string"},
    },
}

OPERATIONS_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "operations"],
    "properties": {
        "summary": {"type": "string"},
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action"],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
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
                        ],
                    },
                    "path": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                    "parent_path": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                    "source_path": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                    "target_path": {"type": "array", "items": {"type": "integer", "minimum": 0}},
                    "index": {"type": "integer", "minimum": 0},
                    "position": {"type": "string", "enum": ["before", "after", "inside"]},
                    "attribute": {"type": "string"},
                    "name": {"type": "string"},
                    "selector": {"type": "string"},
                    "property": {"type": "string"},
                    "value": {},
                    "node": {"type": "object"},
                },
            },
        },
    },
}

# --- Template-creation wizard schemas --------------------------------------
# The hard enforcement for these lives in document_validation.sanitize_document
# (full document) and the wizard views' own bounds-checking (question specs)
# — same "schema shapes the reply, server validates the content" split as
# above.

WIZARD_QUESTIONS_JSON_SCHEMA = {
    "type": "object",
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "label", "type"],
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "type": {"type": "string", "enum": ["text", "textarea", "select"]},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "placeholder": {"type": "string"},
                    "required": {"type": "boolean"},
                },
            },
        },
    },
}

WIZARD_REVIEW_JSON_SCHEMA = {
    "type": "object",
    "required": ["ready"],
    "properties": {
        "ready": {"type": "boolean"},
        # Not a ["string","null"] union: some providers (MiniMax via
        # opencode_zen) reject JSON Schema type arrays outright. The model is
        # told in the prompt to omit/empty this when ready=true, and the
        # Python side (wizard_service.stream_review_answers) already treats
        # a missing/blank value as None.
        "clarification": {"type": "string"},
    },
}

# Split into two calls (structure, then styles) — see WizardAIService.
WIZARD_DOCUMENT_STRUCTURE_JSON_SCHEMA = {
    "type": "object",
    "required": ["name", "summary", "document"],
    "properties": {
        "name": {"type": "string"},
        "summary": {"type": "string"},
        "document": {"type": "object"},
    },
}

WIZARD_STYLES_JSON_SCHEMA = {
    "type": "object",
    "required": ["styles"],
    "properties": {
        "styles": {"type": "object"},
    },
}
