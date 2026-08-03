"""RED tests for the combined generate-and-link endpoint (see spec's
"Combined Generate-And-Link Endpoint" / "Regenerate Overwrites Existing
Link" / "Product Status Gate" / "Endpoint Test Coverage" requirements).
Uses FakeHotmartClient + a mocked WizardAIService.stream_generate_document
so the whole suite runs green with zero live credentials, same seam as
tests/test_ai_wizard.py."""

import pytest

from apps.ai_assistant.document_validation import DocumentValidationError
from apps.ai_assistant.providers import AIProviderError, AIProviderTimeout
from apps.ai_assistant.wizard_service import WizardDocumentResult
from apps.editor.models import AuditEvent, UserTemplate
from apps.hotmart.client import FakeHotmartClient
from apps.hotmart.models import HotmartConnection, HotmartProductLink
from tests.sse_helpers import parse_sse, sse_body

pytestmark = pytest.mark.django_db

GENERATE_URL = "/api/hotmart/products/{product_id}/generate/"

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
        "head": {"title": "Mi producto", "metas": [], "links": [], "scripts": []},
        "body": {"attributes": {}, "children": []},
    },
    "styles": {"variables": {}, "rules": [], "keyframes": []},
    "components": {},
    "assets": {},
}

VALID_ANSWERS = {
    "audience": "emprendedores digitales",
    "promise": "duplicar sus ventas en 30 días",
    "offer_details": "",
}


def _stream(*events):
    def gen(*args, **kwargs):
        yield from events

    return gen


def _connected(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(access="initial-access", expires_in=3600)
    connection.save()
    return connection


@pytest.fixture(autouse=True)
def _fake_client_by_default(monkeypatch):
    monkeypatch.setattr(
        "apps.hotmart.views.build_hotmart_client", lambda credentials: FakeHotmartClient()
    )


class TestSuccessPath:
    def test_generates_and_links_a_new_landing(self, api, user, mocker):
        _connected(user)
        result = WizardDocumentResult(name="Mi Producto", summary="ok", state=VALID_DOCUMENT)
        mocker.patch(
            "apps.hotmart.views.WizardAIService.stream_generate_document",
            _stream(("reasoning", "pensando..."), ("done", result)),
        )

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS, "checkout_url": "https://hotmart.example.com/checkout/fp1"},
            format="json",
        )

        assert response.status_code == 200
        events = dict(parse_sse(sse_body(response)))
        assert "reasoning" in events
        assert events["done"]["name"] == "Mi Producto"
        assert "editor_url" in events["done"]

        template = UserTemplate.objects.get(pk=events["done"]["template_id"])
        assert template.state == VALID_DOCUMENT
        link = HotmartProductLink.objects.get(pk=events["done"]["link_id"])
        assert link.user_template_id == template.id
        assert link.hotmart_product_id == "fake-product-1"
        assert link.checkout_url == "https://hotmart.example.com/checkout/fp1"
        assert AuditEvent.objects.filter(
            owner=user, action=AuditEvent.Action.AI_WIZARD_GENERATE
        ).exists()

    def test_blank_checkout_url_is_accepted(self, api, user, mocker):
        _connected(user)
        result = WizardDocumentResult(name="Mi Producto", summary="ok", state=VALID_DOCUMENT)
        mocker.patch(
            "apps.hotmart.views.WizardAIService.stream_generate_document",
            _stream(("done", result)),
        )

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code == 200
        events = dict(parse_sse(sse_body(response)))
        link = HotmartProductLink.objects.get(pk=events["done"]["link_id"])
        assert link.checkout_url == ""

    def test_no_uploaded_image_is_a_valid_result(self, api, user, mocker):
        _connected(user)
        result = WizardDocumentResult(name="Mi Producto", summary="ok", state=VALID_DOCUMENT)
        stream = mocker.patch("apps.hotmart.views.WizardAIService.stream_generate_document")
        stream.side_effect = _stream(("done", result))

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code == 200
        sse_body(response)
        assert stream.call_args.kwargs["assets"] == []


class TestRegenerate:
    def test_regenerate_overwrites_in_place(self, api, user, mocker):
        connection = _connected(user)
        template = UserTemplate.objects.create(owner=user, name="Old", state=VALID_DOCUMENT)
        template.publish()
        link = HotmartProductLink.objects.create(
            connection=connection,
            user_template=template,
            hotmart_product_id="fake-product-1",
            product_name="Old name",
            checkout_url="https://hotmart.example.com/checkout/old",
        )
        old_slug = template.public_slug

        new_document = {
            **VALID_DOCUMENT,
            "document": {
                **VALID_DOCUMENT["document"],
                "head": {**VALID_DOCUMENT["document"]["head"], "title": "Nuevo"},
            },
        }
        result = WizardDocumentResult(name="Nuevo nombre", summary="ok", state=new_document)
        mocker.patch(
            "apps.hotmart.views.WizardAIService.stream_generate_document",
            _stream(("done", result)),
        )

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code == 200
        sse_body(response)
        assert HotmartProductLink.objects.filter(hotmart_product_id="fake-product-1").count() == 1
        assert UserTemplate.objects.filter(owner=user).count() == 1

        template.refresh_from_db()
        link.refresh_from_db()
        assert template.name == "Nuevo nombre"
        assert template.state == new_document
        assert template.public_slug == old_slug
        assert template.is_published is True
        assert link.pk == link.pk


class TestProductStatusGate:
    def test_non_active_product_is_rejected(self, api, user, mocker, monkeypatch):
        _connected(user)

        class InactiveClient(FakeHotmartClient):
            def list_products(self, access_token):
                products = super().list_products(access_token)
                return [
                    type(products[0])(
                        id=products[0].id,
                        ucode=products[0].ucode,
                        name=products[0].name,
                        is_active=False,
                        checkout_url=products[0].checkout_url,
                    )
                ]

        monkeypatch.setattr(
            "apps.hotmart.views.build_hotmart_client", lambda credentials: InactiveClient()
        )
        stream = mocker.patch("apps.hotmart.views.WizardAIService.stream_generate_document")

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code == 400
        assert response.data["error"] == "product_not_active"
        stream.assert_not_called()
        assert not UserTemplate.objects.exists()

    def test_unknown_product_is_not_found(self, api, user):
        _connected(user)

        response = api.post(
            GENERATE_URL.format(product_id="does-not-exist"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code == 404


class TestInputValidation:
    def test_unknown_answer_key_is_rejected(self, api, user):
        _connected(user)

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": {**VALID_ANSWERS, "extra_field": "nope"}},
            format="json",
        )

        assert response.status_code == 400

    def test_missing_required_answer_is_rejected(self, api, user):
        _connected(user)

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": {"audience": "", "promise": "", "offer_details": ""}},
            format="json",
        )

        assert response.status_code == 400

    def test_non_https_checkout_url_is_rejected(self, api, user):
        _connected(user)

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS, "checkout_url": "http://insecure.example.com/pay"},
            format="json",
        )

        assert response.status_code == 400


class TestUnauthenticated:
    def test_requires_authentication(self, anon_api):
        response = anon_api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code in (401, 403)


class TestFailureLeavesNoOrphan:
    def test_ai_timeout_writes_nothing(self, api, user, mocker):
        _connected(user)

        def _boom(*args, **kwargs):
            raise AIProviderTimeout("too slow")
            yield  # pragma: no cover - generator shape only

        mocker.patch("apps.hotmart.views.WizardAIService.stream_generate_document", _boom)

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        assert response.status_code == 200
        events = dict(parse_sse(sse_body(response)))
        assert events["error"]["error"] == "ai_timeout"
        assert not UserTemplate.objects.exists()
        assert not HotmartProductLink.objects.exists()

    def test_ai_provider_error_writes_nothing(self, api, user, mocker):
        _connected(user)

        def _boom(*args, **kwargs):
            raise AIProviderError("down")
            yield  # pragma: no cover

        mocker.patch("apps.hotmart.views.WizardAIService.stream_generate_document", _boom)

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        events = dict(parse_sse(sse_body(response)))
        assert events["error"]["error"] == "ai_unavailable"
        assert not UserTemplate.objects.exists()

    def test_invalid_document_writes_nothing(self, api, user, mocker):
        _connected(user)

        def _boom(*args, **kwargs):
            raise DocumentValidationError("bad doc")
            yield  # pragma: no cover

        mocker.patch("apps.hotmart.views.WizardAIService.stream_generate_document", _boom)

        response = api.post(
            GENERATE_URL.format(product_id="fake-product-1"),
            {"answers": VALID_ANSWERS},
            format="json",
        )

        events = dict(parse_sse(sse_body(response)))
        assert events["error"]["error"] == "invalid_document"
        assert not UserTemplate.objects.exists()
