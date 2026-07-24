"""Template-creation wizard endpoints.

Three SSE endpoints mirroring EditorTransformView's pattern (see views.py's
docstring for the shared streaming/error-handling contract): dynamic question
generation, answer review/clarification, and full-document generation. None
of these persist anything server-side — the client saves the final result via
the already-existing POST /api/user-templates/ (UserTemplateViewSet).
"""

import logging
import time

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.editor.palettes import get_palette_preset, user_palette_for_client

from .document_validation import DocumentValidationError
from .providers import AIProviderError, AIProviderTimeout
from .serializers import (
    WizardGenerateRequestSerializer,
    WizardQuestionsRequestSerializer,
    WizardReviewRequestSerializer,
)
from .sse import first_error, sse_event
from .usage_logging import log_ai_usage
from .wizard_service import WizardAIService, WizardValidationError

logger = logging.getLogger(__name__)


class WizardQuestionsView(APIView):
    """POST /api/ai/wizard/questions/ — generate a tailored question set
    from the user's free-text description of the page they want."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_wizard_questions"

    def post(self, request):
        serializer = WizardQuestionsRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "wizard questions invalid input for user %s: %s",
                request.user.pk,
                serializer.errors,
            )
            return Response(
                {"error": "invalid_input", "detail": first_error(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        user_id = request.user.pk
        scope = self.throttle_scope

        def event_stream():
            start_time = time.monotonic()
            outcome = "success"
            try:
                for kind, value in WizardAIService().stream_generate_questions(
                    data["description"], data.get("history", [])
                ):
                    if kind == "reasoning":
                        yield sse_event("reasoning", {"text": value})
                    else:
                        yield sse_event(
                            "done",
                            {"questions": value.questions, "reasoning": value.reasoning},
                        )
            except AIProviderTimeout:
                outcome = "ai_timeout"
                logger.warning("wizard questions timed out for user %s", user_id)
                yield sse_event("error", {"error": "ai_timeout"})
            except AIProviderError:
                outcome = "ai_unavailable"
                logger.exception("wizard questions provider error for user %s", user_id)
                yield sse_event("error", {"error": "ai_unavailable"})
            except WizardValidationError:
                outcome = "invalid_questions"
                logger.warning("wizard produced invalid questions for user %s", user_id)
                yield sse_event("error", {"error": "invalid_questions"})
            except Exception:
                outcome = "unexpected_error"
                logger.exception("Unexpected error during wizard questions for user %s", user_id)
                yield sse_event("error", {"error": "unexpected_error"})
            finally:
                log_ai_usage(scope, user_id, outcome, start_time)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class WizardReviewView(APIView):
    """POST /api/ai/wizard/review/ — decide if the answers gathered so far
    are enough to generate the page, or ask one clarifying question."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_wizard_review"

    def post(self, request):
        serializer = WizardReviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "wizard review invalid input for user %s: %s",
                request.user.pk,
                serializer.errors,
            )
            return Response(
                {"error": "invalid_input", "detail": first_error(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        user_id = request.user.pk
        scope = self.throttle_scope

        def event_stream():
            start_time = time.monotonic()
            outcome = "success"
            try:
                for kind, value in WizardAIService().stream_review_answers(
                    data["description"], data["answers"], data.get("history", [])
                ):
                    if kind == "reasoning":
                        yield sse_event("reasoning", {"text": value})
                    else:
                        yield sse_event(
                            "done",
                            {
                                "ready": value.ready,
                                "clarification": value.clarification,
                                "reasoning": value.reasoning,
                            },
                        )
            except AIProviderTimeout:
                outcome = "ai_timeout"
                logger.warning("wizard review timed out for user %s", user_id)
                yield sse_event("error", {"error": "ai_timeout"})
            except AIProviderError:
                outcome = "ai_unavailable"
                logger.exception("wizard review provider error for user %s", user_id)
                yield sse_event("error", {"error": "ai_unavailable"})
            except Exception:
                outcome = "unexpected_error"
                logger.exception("Unexpected error during wizard review for user %s", user_id)
                yield sse_event("error", {"error": "unexpected_error"})
            finally:
                log_ai_usage(scope, user_id, outcome, start_time)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class WizardGenerateView(APIView):
    """POST /api/ai/wizard/generate/ — generate the full page document from
    the accumulated description + answers + clarification chat."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_wizard_generate"

    def post(self, request):
        serializer = WizardGenerateRequestSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            logger.warning(
                "wizard generate invalid input for user %s: %s",
                request.user.pk,
                serializer.errors,
            )
            return Response(
                {"error": "invalid_input", "detail": first_error(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        user_id = request.user.pk
        scope = self.throttle_scope
        palette_id = data.get("palette_id")
        selected_palette = get_palette_preset(palette_id)
        if selected_palette is None and palette_id:
            user_palette = request.user.user_palettes.filter(slug=palette_id).first()
            if user_palette is None:
                return Response(
                    {"error": "invalid_input", "detail": "unknown palette"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            selected_palette = user_palette_for_client(user_palette)

        def event_stream():
            start_time = time.monotonic()
            outcome = "success"
            try:
                for kind, value in WizardAIService().stream_generate_document(
                    data["description"],
                    data["answers"],
                    data.get("history", []),
                    assets=data.get("assets", []),
                    palette_id=palette_id,
                    selected_palette=selected_palette,
                ):
                    if kind == "reasoning":
                        yield sse_event("reasoning", {"text": value})
                    else:
                        yield sse_event(
                            "done",
                            {
                                "name": value.name,
                                "summary": value.summary,
                                "state": value.state,
                                "reasoning": value.reasoning,
                            },
                        )
            except AIProviderTimeout:
                outcome = "ai_timeout"
                logger.warning("wizard generate timed out for user %s", user_id)
                yield sse_event("error", {"error": "ai_timeout"})
            except AIProviderError:
                outcome = "ai_unavailable"
                logger.exception("wizard generate provider error for user %s", user_id)
                yield sse_event("error", {"error": "ai_unavailable"})
            except DocumentValidationError:
                outcome = "invalid_document"
                logger.warning("wizard produced an invalid document for user %s", user_id)
                yield sse_event("error", {"error": "invalid_document"})
            except Exception:
                outcome = "unexpected_error"
                logger.exception("Unexpected error during wizard generate for user %s", user_id)
                yield sse_event("error", {"error": "unexpected_error"})
            finally:
                log_ai_usage(scope, user_id, outcome, start_time)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
