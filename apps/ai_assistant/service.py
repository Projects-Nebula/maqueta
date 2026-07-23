"""Editor AI service: turns an editor context into validated operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from django.conf import settings

from .operations import OperationValidationError, validate_operations
from .prompts import EDITOR_CLARIFY_PROMPT, SYSTEM_PROMPT
from .providers import AIProvider, AIProviderError, build_provider
from .schema import EDITOR_CLARIFY_JSON_SCHEMA, OPERATIONS_JSON_SCHEMA

logger = logging.getLogger(__name__)


@dataclass
class EditorContext:
    instruction: str
    selected_path: list | None = None
    selected_node: dict | None = None
    parent_context: dict = field(default_factory=dict)
    sibling_context: list = field(default_factory=list)
    design_variables: dict = field(default_factory=dict)
    page_summary: dict = field(default_factory=dict)
    body_outline: list = field(default_factory=list)
    global_mode: bool = False
    history: list = field(default_factory=list)
    available_products: list = field(default_factory=list)
    available_gateways: list = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "instruction": self.instruction,
            "selected_path": self.selected_path,
            "selected_node": self.selected_node,
            "parent_context": self.parent_context,
            "sibling_context": self.sibling_context,
            "design_variables": self.design_variables,
            "page_summary": self.page_summary,
            "body_outline": self.body_outline,
            "global_mode": self.global_mode,
            "available_products": self.available_products,
            "available_gateways": self.available_gateways,
        }


@dataclass
class EditorAIResult:
    summary: str
    operations: list
    reasoning: str | None = None


class EditorAIService:
    """Coordinates the provider calls and validates their output.

    Two providers, two roles — same split as the template wizard:
    ``chat_provider`` (OPENCODE_ZEN_CHAT_MODEL, a conversational model)
    turns the user's raw instruction into a clear, unambiguous one using page
    context; ``provider`` (the main OPENCODE_ZEN_MODEL) then generates
    operations from that clarified instruction, so it only has to execute,
    not also resolve ambiguity.
    """

    def __init__(self, provider: AIProvider | None = None, chat_provider: AIProvider | None = None):
        self._provider = provider or build_provider(settings)
        self._chat_provider = chat_provider or build_provider(
            settings, model=settings.OPENCODE_ZEN_CHAT_MODEL
        )

    def _clarify_instruction(self, context: EditorContext):
        """Yield ("reasoning", text) chunks, then a final ("instruction", text).

        Best-effort: rewrites the raw instruction to be explicit, falling
        back to the raw instruction on any provider failure — clarifying is
        an enhancement, not a hard requirement for editing to work."""
        try:
            for kind, value in self._chat_provider.stream_generate(
                system_prompt=EDITOR_CLARIFY_PROMPT,
                history=context.history,
                payload=context.to_payload(),
                schema=EDITOR_CLARIFY_JSON_SCHEMA,
            ):
                if kind == "reasoning":
                    yield "reasoning", value
                    continue
                raw = value
                candidate = raw.get("instruction") if isinstance(raw, dict) else None
                if isinstance(candidate, str) and candidate.strip():
                    yield "instruction", candidate.strip()[:2000]
                    return
        except AIProviderError:
            logger.warning("editor instruction clarification failed; using raw instruction")
        yield "instruction", context.instruction

    def stream_generate_operations(self, context: EditorContext):
        """Yield ("reasoning", text) chunks as the models think, then a
        final ("done", EditorAIResult) once the output has been validated.

        Nothing is applied until the terminal event: operations are only
        exposed after validate_operations has accepted the whole batch.
        """
        clarified_instruction = context.instruction
        for kind, value in self._clarify_instruction(context):
            if kind == "reasoning":
                yield "reasoning", value
            else:
                clarified_instruction = value
        clarified_context = replace(context, instruction=clarified_instruction)

        for kind, value in self._provider.stream_generate(
            system_prompt=SYSTEM_PROMPT,
            history=context.history,
            payload=clarified_context.to_payload(),
            schema=OPERATIONS_JSON_SCHEMA,
        ):
            if kind == "reasoning":
                yield "reasoning", value
                continue
            raw = value
            summary = raw.get("summary", "") if isinstance(raw, dict) else ""
            operations = raw.get("operations") if isinstance(raw, dict) else None
            reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
            # Raises OperationValidationError on anything unsafe/malformed.
            try:
                validate_operations(operations, max_operations=settings.AI_MAX_OPERATIONS)
            except OperationValidationError:
                logger.debug("rejected AI operations: %r", operations)
                raise
            yield (
                "done",
                EditorAIResult(
                    summary=str(summary)[:500],
                    operations=operations,
                    reasoning=str(reasoning)[:4000] if reasoning else None,
                ),
            )
