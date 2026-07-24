import logging

import pytest

from apps.ai_assistant.document_validation import DocumentValidationError
from apps.ai_assistant.providers import AIProviderError, AIProviderTimeout
from apps.ai_assistant.wizard_service import (
    WizardDocumentResult,
    WizardQuestionsResult,
    WizardReviewResult,
)
from apps.editor.models import UserPalette
from tests.sse_helpers import parse_sse, sse_body

pytestmark = pytest.mark.django_db

QUESTIONS_URL = "/api/ai/wizard/questions/"
REVIEW_URL = "/api/ai/wizard/review/"
GENERATE_URL = "/api/ai/wizard/generate/"

VALID_DOCUMENT = {
    "schemaVersion": "2.0",
    "settings": {
        "strict": True,
        "escapeText": True,
        "allowRawHtml": False,
        "allowInlineScripts": False,
        "requireImageAlt": True,
        "requireUniqueIds": True,
    },
    "document": {
        "doctype": "html",
        "htmlAttributes": {"lang": "es", "dir": "ltr"},
        "head": {"title": "Mi negocio", "metas": [], "links": [], "scripts": []},
        "body": {"attributes": {}, "children": []},
    },
    "styles": {"variables": {}, "rules": [], "keyframes": []},
    "components": {},
    "assets": {},
}


def _stream(*events):
    """Build a fake generator matching WizardAIService's ("kind", value) shape."""

    def gen(*args, **kwargs):
        yield from events

    return gen


# --- auth ---------------------------------------------------------------


def test_questions_requires_authentication(anon_api):
    response = anon_api.post(QUESTIONS_URL, {"description": "una landing"}, format="json")
    assert response.status_code in (401, 403)


def test_review_requires_authentication(anon_api):
    response = anon_api.post(REVIEW_URL, {"description": "x", "answers": {}}, format="json")
    assert response.status_code in (401, 403)


def test_generate_requires_authentication(anon_api):
    response = anon_api.post(GENERATE_URL, {"description": "x", "answers": {}}, format="json")
    assert response.status_code in (401, 403)


def test_generate_rejects_unknown_palette_preset(api):
    response = api.post(
        GENERATE_URL,
        {"description": "x", "answers": {}, "palette_id": "not-a-preset"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_resolves_only_the_current_users_saved_palette(api, user, mocker):
    palette = UserPalette.objects.create(
        owner=user,
        slug="custom-mi-marca",
        name="Mi marca",
        variables={
            "--color-primary": "#112233",
            "--color-background": "#f8fafc",
            "--color-text": "#0f172a",
            "--color-surface": "#ffffff",
        },
    )
    result = WizardDocumentResult(name="Mi template", summary="ok", state=VALID_DOCUMENT)
    stream = mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_generate_document")
    stream.side_effect = _stream(("done", result))

    response = api.post(
        GENERATE_URL,
        {"description": "x", "answers": {}, "palette_id": palette.slug},
        format="json",
    )

    assert response.status_code == 200
    sse_body(response)
    assert stream.call_args.kwargs["selected_palette"]["id"] == palette.slug
    assert stream.call_args.kwargs["selected_palette"]["source"] == "custom"


# --- questions ------------------------------------------------------------


def test_questions_returns_generated_form(api, mocker):
    result = WizardQuestionsResult(
        questions=[{"id": "brand", "label": "¿Nombre de marca?", "type": "text"}],
    )
    mocker.patch(
        "apps.ai_assistant.wizard_views.WizardAIService.stream_generate_questions",
        _stream(("reasoning", "pensando..."), ("done", result)),
    )
    response = api.post(QUESTIONS_URL, {"description": "una landing de skincare"}, format="json")
    assert response.status_code == 200
    events = dict(parse_sse(sse_body(response)))
    assert events["done"]["questions"] == result.questions


def test_questions_rejects_oversized_payload(api, settings):
    settings.AI_MAX_INPUT_CHARACTERS = 10
    response = api.post(QUESTIONS_URL, {"description": "una landing de skincare"}, format="json")
    assert response.status_code == 400


def test_questions_timeout_reported_as_error_event(api, mocker):
    def gen(*args, **kwargs):
        raise AIProviderTimeout("slow")
        yield  # pragma: no cover - makes this a generator

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_generate_questions", gen)
    response = api.post(QUESTIONS_URL, {"description": "x"}, format="json")
    assert response.status_code == 200
    assert dict(parse_sse(sse_body(response)))["error"] == {"error": "ai_timeout"}


# --- review -----------------------------------------------------------------


def test_review_ready_true_short_circuits(api, mocker):
    result = WizardReviewResult(ready=True, clarification=None)
    mocker.patch(
        "apps.ai_assistant.wizard_views.WizardAIService.stream_review_answers",
        _stream(("done", result)),
    )
    response = api.post(
        REVIEW_URL,
        {"description": "x", "answers": {"brand": "GlowSkin"}},
        format="json",
    )
    assert response.status_code == 200
    assert dict(parse_sse(sse_body(response)))["done"]["ready"] is True


def test_review_ready_false_returns_clarification(api, mocker):
    result = WizardReviewResult(ready=False, clarification="¿Qué colores preferís?")
    mocker.patch(
        "apps.ai_assistant.wizard_views.WizardAIService.stream_review_answers",
        _stream(("done", result)),
    )
    response = api.post(
        REVIEW_URL,
        {"description": "x", "answers": {"brand": "GlowSkin"}},
        format="json",
    )
    assert response.status_code == 200
    done = dict(parse_sse(sse_body(response)))["done"]
    assert done["ready"] is False
    assert done["clarification"] == "¿Qué colores preferís?"


def test_review_rejects_invalid_answers_shape(api):
    response = api.post(
        REVIEW_URL,
        {"description": "x", "answers": "not-a-dict"},
        format="json",
    )
    assert response.status_code == 400


def test_review_provider_error_does_not_leak_internals(api, mocker):
    def gen(*args, **kwargs):
        raise AIProviderError("secret-internal-detail")
        yield  # pragma: no cover

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_review_answers", gen)
    response = api.post(REVIEW_URL, {"description": "x", "answers": {}}, format="json")
    body = sse_body(response)
    assert dict(parse_sse(body))["error"] == {"error": "ai_unavailable"}
    assert "secret-internal-detail" not in body.decode()


# --- generate -----------------------------------------------------------------


def test_generate_returns_sanitized_document(api, mocker):
    result = WizardDocumentResult(
        name="GlowSkin", summary="Landing de skincare", state=VALID_DOCUMENT
    )
    mocker.patch(
        "apps.ai_assistant.wizard_views.WizardAIService.stream_generate_document",
        _stream(("done", result)),
    )
    response = api.post(
        GENERATE_URL,
        {"description": "x", "answers": {"brand": "GlowSkin"}},
        format="json",
    )
    assert response.status_code == 200
    done = dict(parse_sse(sse_body(response)))["done"]
    assert done["name"] == "GlowSkin"
    assert done["state"] == VALID_DOCUMENT


def test_generate_rejects_unsafe_document(api, mocker):
    def gen(*args, **kwargs):
        raise DocumentValidationError("scripts must be empty")
        yield  # pragma: no cover

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_generate_document", gen)
    response = api.post(
        GENERATE_URL,
        {"description": "x", "answers": {}},
        format="json",
    )
    assert response.status_code == 200
    assert dict(parse_sse(sse_body(response)))["error"] == {"error": "invalid_document"}


# --- unexpected errors: caught, logged, don't crash the stream ------------


def test_questions_unexpected_error_is_caught(api, mocker, caplog):
    def gen(*args, **kwargs):
        raise KeyError("unexpected shape")
        yield  # pragma: no cover

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_generate_questions", gen)
    response = api.post(QUESTIONS_URL, {"description": "x"}, format="json")
    assert response.status_code == 200
    assert dict(parse_sse(sse_body(response)))["error"] == {"error": "unexpected_error"}
    assert "Unexpected error during wizard questions" in caplog.text


def test_review_unexpected_error_is_caught(api, mocker, caplog):
    def gen(*args, **kwargs):
        raise KeyError("unexpected shape")
        yield  # pragma: no cover

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_review_answers", gen)
    response = api.post(REVIEW_URL, {"description": "x", "answers": {}}, format="json")
    assert response.status_code == 200
    assert dict(parse_sse(sse_body(response)))["error"] == {"error": "unexpected_error"}
    assert "Unexpected error during wizard review" in caplog.text


def test_generate_unexpected_error_is_caught(api, mocker, caplog):
    def gen(*args, **kwargs):
        raise KeyError("unexpected shape")
        yield  # pragma: no cover

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_generate_document", gen)
    response = api.post(GENERATE_URL, {"description": "x", "answers": {}}, format="json")
    assert response.status_code == 200
    assert dict(parse_sse(sse_body(response)))["error"] == {"error": "unexpected_error"}
    assert "Unexpected error during wizard generate" in caplog.text


# --- structured usage logging ----------------------------------------------


def test_usage_log_line_emitted_on_success(api, mocker, caplog):
    result = WizardQuestionsResult(questions=[])
    mocker.patch(
        "apps.ai_assistant.wizard_views.WizardAIService.stream_generate_questions",
        _stream(("done", result)),
    )
    with caplog.at_level(logging.INFO, logger="ai.usage"):
        response = api.post(QUESTIONS_URL, {"description": "x"}, format="json")
        sse_body(response)  # the usage log line fires when the generator finishes
    assert "ai_usage scope=ai_wizard_questions" in caplog.text
    assert "outcome=success" in caplog.text


def test_usage_log_line_emitted_on_error(api, mocker, caplog):
    def gen(*args, **kwargs):
        raise AIProviderTimeout("slow")
        yield  # pragma: no cover

    mocker.patch("apps.ai_assistant.wizard_views.WizardAIService.stream_generate_questions", gen)
    with caplog.at_level(logging.INFO, logger="ai.usage"):
        response = api.post(QUESTIONS_URL, {"description": "x"}, format="json")
        sse_body(response)
    assert "ai_usage scope=ai_wizard_questions" in caplog.text
    assert "outcome=ai_timeout" in caplog.text
