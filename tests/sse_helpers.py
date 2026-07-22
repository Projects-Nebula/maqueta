"""Shared helpers for testing the SSE-streaming AI endpoints."""

import json


def sse_body(response) -> bytes:
    return b"".join(response.streaming_content)


def parse_sse(content: bytes):
    """Parse a Server-Sent Events body into [(event, data), ...]."""
    events = []
    for block in content.decode().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = "message"
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        events.append((event_name, data))
    return events
