"""Small shared helpers for the SSE-streaming AI endpoints."""

import json


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def first_error(errors) -> str:
    """Flatten DRF serializer errors to one short human-readable string."""
    if isinstance(errors, dict):
        for key, value in errors.items():
            msg = first_error(value)
            return msg if key in ("non_field_errors",) else f"{key}: {msg}"
    if isinstance(errors, (list, tuple)) and errors:
        return first_error(errors[0])
    return str(errors)
