"""Template-creation wizard AI service.

Four AI calls make up the guided "create a custom template" flow: a dynamic
question set tailored to the user's free-text description, a review step
that decides whether more clarification is needed, and finally document
generation split into two calls — structure (the HTML tree), then styles
(the CSS for the classes that structure introduced). See wizard_views.py for
the HTTP layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from .document_validation import DocumentValidationError, sanitize_document
from .prompts import (
    WIZARD_DOCUMENT_STRUCTURE_PROMPT,
    WIZARD_QUESTIONS_PROMPT,
    WIZARD_REVIEW_PROMPT,
    WIZARD_STYLES_PROMPT,
)
from .providers import AIProvider, build_provider
from .schema import (
    WIZARD_DOCUMENT_STRUCTURE_JSON_SCHEMA,
    WIZARD_QUESTIONS_JSON_SCHEMA,
    WIZARD_REVIEW_JSON_SCHEMA,
    WIZARD_STYLES_JSON_SCHEMA,
)

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 8
MAX_LABEL_LENGTH = 300
MAX_OPTIONS = 12
ALLOWED_QUESTION_TYPES = {"text", "textarea", "select"}


class WizardValidationError(ValueError):
    """Raised when the AI's dynamic question spec is malformed or unsafe."""


def _validate_questions(questions) -> list:
    if not isinstance(questions, list) or not questions:
        raise WizardValidationError("questions must be a non-empty list")
    if len(questions) > MAX_QUESTIONS:
        raise WizardValidationError("too many questions")
    seen_ids = set()
    for q in questions:
        if not isinstance(q, dict):
            raise WizardValidationError("each question must be an object")
        qid = q.get("id")
        if not isinstance(qid, str) or not qid.strip() or qid in seen_ids:
            raise WizardValidationError("invalid or duplicate question id")
        seen_ids.add(qid)
        label = q.get("label")
        if not isinstance(label, str) or not label.strip() or len(label) > MAX_LABEL_LENGTH:
            raise WizardValidationError("invalid question label")
        qtype = q.get("type")
        if qtype not in ALLOWED_QUESTION_TYPES:
            raise WizardValidationError(f"invalid question type: {qtype}")
        if qtype == "select":
            options = q.get("options")
            if not isinstance(options, list) or not options or len(options) > MAX_OPTIONS:
                raise WizardValidationError("select question needs options")
            for opt in options:
                if not isinstance(opt, str) or not opt.strip() or len(opt) > MAX_LABEL_LENGTH:
                    raise WizardValidationError("invalid option value")
    return questions


@dataclass
class WizardQuestionsResult:
    questions: list
    reasoning: str | None = None


@dataclass
class WizardReviewResult:
    ready: bool
    clarification: str | None = None
    reasoning: str | None = None


@dataclass
class WizardDocumentResult:
    name: str
    summary: str
    state: dict
    reasoning: str | None = None


class WizardAIService:
    """Coordinates the three wizard AI calls and validates their output.

    Two providers, two roles: ``chat_provider`` (OPENCODE_ZEN_CHAT_MODEL, a
    more conversational model) drives the two chat-like calls — dynamic
    question generation and answer review — while ``provider`` (the main
    OPENCODE_ZEN_MODEL) handles the one heavy structured-JSON call, full
    document generation, where reliability at strict large-JSON output
    matters more than conversational tone.
    """

    def __init__(self, provider: AIProvider | None = None, chat_provider: AIProvider | None = None):
        self._provider = provider or build_provider(settings)
        self._chat_provider = chat_provider or build_provider(
            settings, model=settings.OPENCODE_ZEN_CHAT_MODEL
        )

    def stream_generate_questions(self, description: str, history: list):
        """Yield ("reasoning", text) chunks, then ("done", WizardQuestionsResult)."""
        for kind, value in self._chat_provider.stream_generate(
            system_prompt=WIZARD_QUESTIONS_PROMPT,
            history=history,
            payload={"description": description},
            schema=WIZARD_QUESTIONS_JSON_SCHEMA,
        ):
            if kind == "reasoning":
                yield "reasoning", value
                continue
            raw = value
            questions = raw.get("questions") if isinstance(raw, dict) else None
            reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
            try:
                _validate_questions(questions)
            except WizardValidationError:
                logger.debug("rejected AI question spec: %r", questions)
                raise
            yield (
                "done",
                WizardQuestionsResult(
                    questions=questions,
                    reasoning=str(reasoning)[:4000] if reasoning else None,
                ),
            )

    def stream_review_answers(self, description: str, answers: dict, history: list):
        """Yield ("reasoning", text) chunks, then ("done", WizardReviewResult)."""
        for kind, value in self._chat_provider.stream_generate(
            system_prompt=WIZARD_REVIEW_PROMPT,
            history=history,
            payload={"description": description, "answers": answers},
            schema=WIZARD_REVIEW_JSON_SCHEMA,
        ):
            if kind == "reasoning":
                yield "reasoning", value
                continue
            raw = value
            ready = bool(raw.get("ready")) if isinstance(raw, dict) else False
            clarification = raw.get("clarification") if isinstance(raw, dict) else None
            reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
            if not ready and not (isinstance(clarification, str) and clarification.strip()):
                # "not ready" with no actual question would stall the wizard
                # on nothing — treat as ready rather than looping forever.
                ready = True
                clarification = None
            yield (
                "done",
                WizardReviewResult(
                    ready=ready,
                    clarification=str(clarification)[:1000] if clarification else None,
                    reasoning=str(reasoning)[:4000] if reasoning else None,
                ),
            )

    def stream_generate_document(
        self, description: str, answers: dict, history: list, assets: list | None = None
    ):
        """Yield ("reasoning", text) chunks from both phases, then a final
        ("done", WizardDocumentResult).

        Two calls instead of one: structure (the HTML tree) first, then
        styles for the classes that structure introduced — using the body
        already generated as context so selectors actually match. Asking
        for both in one shot was where the model most often ran out of
        steam and silently dropped the trailing styles/components/assets
        keys; each call alone is shorter and finishes more reliably.
        Nothing is exposed until the terminal event: the assembled document
        is only returned after sanitize_document has accepted it whole.
        """
        reasoning_parts = []
        name = ""
        summary = ""
        skeleton = None
        available_images = [
            {"url": a["url"], "width": a["width"], "height": a["height"]} for a in (assets or [])
        ]
        for kind, value in self._provider.stream_generate(
            system_prompt=WIZARD_DOCUMENT_STRUCTURE_PROMPT,
            history=history,
            payload={
                "description": description,
                "answers": answers,
                "available_images": available_images,
            },
            schema=WIZARD_DOCUMENT_STRUCTURE_JSON_SCHEMA,
        ):
            if kind == "reasoning":
                yield "reasoning", value
                continue
            raw = value
            name = raw.get("name", "") if isinstance(raw, dict) else ""
            summary = raw.get("summary", "") if isinstance(raw, dict) else ""
            skeleton = raw.get("document") if isinstance(raw, dict) else None
            raw_reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
            if raw_reasoning:
                reasoning_parts.append(raw_reasoning)

        if not isinstance(skeleton, dict):
            logger.debug("wizard structure call returned no document: %r", skeleton)
            raise DocumentValidationError("missing document structure")

        # No components feature exists yet — force empty rather than trust
        # the model to keep echoing back an always-empty boilerplate value:
        # it reliably omits it under load, which used to fail the whole
        # generation over nothing worth generating.
        skeleton["components"] = {}
        # Built server-side from the user's own already-uploaded, already
        # validated images — never from the model's own JSON, so a
        # malformed/hallucinated entry here can't happen by construction.
        # The model only ever picks a URL from this same list to put in an
        # <img src>; it never authors the assets registry itself.
        skeleton["assets"] = {
            f"asset-{i}": {"url": img["url"], "width": img["width"], "height": img["height"]}
            for i, img in enumerate(available_images)
        }

        body = (skeleton.get("document") or {}).get("body")

        styles = None
        for kind, value in self._provider.stream_generate(
            system_prompt=WIZARD_STYLES_PROMPT,
            history=history,
            payload={"description": description, "answers": answers, "body": body},
            schema=WIZARD_STYLES_JSON_SCHEMA,
        ):
            if kind == "reasoning":
                yield "reasoning", value
                continue
            raw = value
            styles = raw.get("styles") if isinstance(raw, dict) else None
            raw_reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
            if raw_reasoning:
                reasoning_parts.append(raw_reasoning)

        document = {**skeleton, "styles": styles}
        try:
            sanitize_document(document)
        except DocumentValidationError as exc:
            # Kept at INFO (not DEBUG) permanently: the model's output isn't
            # deterministic, so a rejection here doesn't reliably reproduce
            # on retry — the reason needs to already be in the log the first
            # time it happens, not require flipping the level and asking the
            # user to trigger it again.
            logger.info("rejected AI-generated document: %s", exc)
            raise

        yield (
            "done",
            WizardDocumentResult(
                name=str(name)[:200] or "Mi template",
                summary=str(summary)[:500],
                state=document,
                reasoning="\n\n".join(reasoning_parts)[:4000] if reasoning_parts else None,
            ),
        )
