"""AI transform endpoint."""

import logging
import time

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.storefront.models import Product

from .operations import OperationValidationError
from .providers import AIProviderError, AIProviderTimeout
from .serializers import TransformRequestSerializer
from .service import EditorAIService, EditorContext
from .sse import first_error, sse_event
from .usage_logging import log_ai_usage

logger = logging.getLogger(__name__)


class EditorTransformView(APIView):
    """POST /api/ai/editor/transform/ — stream reasoning, then validated ops.

    Server-Sent Events: zero or more "reasoning" chunks while the model
    thinks, followed by one terminal "done" (validated operations) or
    "error" event. Input validation still happens synchronously before any
    streaming starts, so malformed requests get a normal 400 response — but
    once streaming begins the HTTP status is committed at 200, so provider
    failures travel as an in-band "error" event instead of a status code.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_transform"

    def post(self, request):
        serializer = TransformRequestSerializer(data=request.data)
        if not serializer.is_valid():
            # Surface WHY the request was rejected (logged for us, coded for the UI).
            logger.warning(
                "transform invalid input for user %s: %s",
                request.user.pk,
                serializer.errors,
            )
            return Response(
                {"error": "invalid_input", "detail": first_error(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data

        # Populated server-side from the requesting user's own products —
        # never trust a client-supplied product list, since the model would
        # otherwise have no way to tell a real id from a made-up one.
        available_products = [
            {
                "id": product.id,
                "name": product.name,
                "price_cents": product.price_cents,
                "image_url": product.image.file.url if product.image else None,
            }
            for product in Product.objects.filter(owner=request.user, is_active=True)
        ]

        context = EditorContext(
            instruction=data["instruction"],
            selected_path=data.get("selected_path"),
            selected_node=data.get("selected_node"),
            parent_context=data.get("parent_context", {}),
            sibling_context=data.get("sibling_context", []),
            design_variables=data.get("design_variables", {}),
            page_summary=data.get("page_summary", {}),
            body_outline=data.get("body_outline", []),
            global_mode=data.get("global_mode", False),
            history=data.get("history", []),
            available_products=available_products,
        )
        user_id = request.user.pk
        scope = self.throttle_scope

        def event_stream():
            start_time = time.monotonic()
            outcome = "success"
            try:
                for kind, value in EditorAIService().stream_generate_operations(context):
                    if kind == "reasoning":
                        yield sse_event("reasoning", {"text": value})
                    else:
                        yield sse_event(
                            "done",
                            {
                                "summary": value.summary,
                                "operations": value.operations,
                                "reasoning": value.reasoning,
                            },
                        )
            except AIProviderTimeout:
                outcome = "ai_timeout"
                logger.warning("AI transform timed out for user %s", user_id)
                yield sse_event("error", {"error": "ai_timeout"})
            except AIProviderError:
                # Do not leak provider internals to the client.
                outcome = "ai_unavailable"
                logger.exception("AI provider error for user %s", user_id)
                yield sse_event("error", {"error": "ai_unavailable"})
            except OperationValidationError as exc:
                outcome = "invalid_operations"
                logger.warning("AI produced invalid operations for user %s: %s", user_id, exc)
                yield sse_event("error", {"error": "invalid_operations"})
            except Exception:
                # Anything else (parsing bugs, provider response shape drift, etc.)
                # would otherwise crash the stream generator uncaught, turning into
                # a bare connection drop the client can't distinguish from a real
                # provider outage. Log the real traceback so it's diagnosable.
                outcome = "unexpected_error"
                logger.exception("Unexpected error during AI transform for user %s", user_id)
                yield sse_event("error", {"error": "unexpected_error"})
            finally:
                log_ai_usage(scope, user_id, outcome, start_time)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
