"""Structured (logfmt-style) usage logging for the AI SSE endpoints.

Greppable request counts, outcomes, and latency per scope/user without
adding a metrics dependency — parse `ai_usage ...` lines from the log if a
real metrics pipeline is ever wired up.
"""

import logging
import time

logger = logging.getLogger("ai.usage")


def log_ai_usage(scope: str, user_id, outcome: str, start_time: float) -> None:
    duration_ms = int((time.monotonic() - start_time) * 1000)
    logger.info(
        "ai_usage scope=%s user=%s outcome=%s duration_ms=%d",
        scope,
        user_id,
        outcome,
        duration_ms,
    )
