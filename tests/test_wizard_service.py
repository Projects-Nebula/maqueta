from apps.ai_assistant.wizard_service import WizardAIService

VALID_SKELETON = {
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
        "body": {
            "attributes": {"class": ["flex", "flex-col"]},
            "children": [{"type": "element", "tag": "h1", "attributes": {}, "children": []}],
        },
    },
    # Deliberately omitted here — the model does this under load; the service
    # must force them back in rather than fail the whole generation.
}

VALID_STYLES = {
    "variables": {
        "--color-primary": "#0f766e",
        "--color-background": "#f0fdfa",
        "--color-text": "#134e4a",
        "--color-surface": "#ffffff",
    },
    "rules": [],
    "mediaQueries": [],
    "keyframes": [],
}


class _StubProvider:
    """Returns a canned ("done", raw_dict) for each successive call,
    matching AIProvider.stream_generate's ("kind", value) protocol."""

    def __init__(self, responses):
        self._responses = iter(responses)

    def stream_generate(self, *, system_prompt, payload, schema, history=None):
        yield "done", next(self._responses)


def test_generate_document_forces_components_and_assets_even_if_model_omits_them():
    provider = _StubProvider(
        [
            {"name": "Mi Negocio", "summary": "resumen", "document": dict(VALID_SKELETON)},
            {"styles": VALID_STYLES},
        ]
    )
    service = WizardAIService(provider=provider, chat_provider=provider)

    events = list(service.stream_generate_document("desc", {"brand": "x"}, []))

    done_events = [v for k, v in events if k == "done"]
    assert len(done_events) == 1
    state = done_events[0].state
    assert state["components"] == {}
    assert state["assets"] == {}
    assert state["styles"]["variables"] == VALID_STYLES["variables"]
    assert state["styles"]["palette"] == {
        "id": "ai-generated",
        "name": "Paleta generada",
        "source": "ai",
    }
    assert state["styles"]["rules"] == []


def test_generate_document_registers_provided_assets_server_side():
    # The model's own JSON never controls assets — even if it tried to
    # hallucinate an entry, the service overwrites it with exactly what the
    # (already-uploaded, already-validated) client-provided list says.
    skeleton_with_hallucinated_assets = {
        **VALID_SKELETON,
        "assets": {"hallucinated": {"url": "https://evil.example/x.png"}},
    }
    provider = _StubProvider(
        [
            {
                "name": "Mi Negocio",
                "summary": "resumen",
                "document": skeleton_with_hallucinated_assets,
            },
            {"styles": VALID_STYLES},
        ]
    )
    service = WizardAIService(provider=provider, chat_provider=provider)

    assets = [{"id": "a1", "url": "/media/wizard-uploads/x.jpg", "width": 800, "height": 600}]
    events = list(service.stream_generate_document("desc", {"brand": "x"}, [], assets=assets))

    state = [v for k, v in events if k == "done"][0].state
    assert state["assets"] == {
        "asset-0": {"url": "/media/wizard-uploads/x.jpg", "width": 800, "height": 600}
    }


def test_generate_document_uses_selected_preset_without_ai_overwriting_it():
    provider = _StubProvider(
        [{"name": "Mi Negocio", "summary": "resumen", "document": dict(VALID_SKELETON)}]
    )
    service = WizardAIService(provider=provider, chat_provider=provider)

    events = list(service.stream_generate_document("desc", {"brand": "x"}, [], palette_id="forest"))

    state = [v for k, v in events if k == "done"][0].state
    assert state["styles"]["palette"] == {
        "id": "forest",
        "name": "Bosque",
        "source": "preset",
    }
    assert state["styles"]["variables"]["--color-primary"] == "#166534"


def test_generate_document_uses_selected_user_palette_without_ai_overwriting_it():
    provider = _StubProvider(
        [{"name": "Mi Negocio", "summary": "resumen", "document": dict(VALID_SKELETON)}]
    )
    selected_palette = {
        "id": "custom-mi-marca",
        "name": "Mi marca",
        "description": "Paleta guardada.",
        "source": "custom",
        "variables": {
            "--color-primary": "#112233",
            "--color-background": "#f8fafc",
            "--color-text": "#0f172a",
            "--color-surface": "#ffffff",
        },
    }
    service = WizardAIService(provider=provider, chat_provider=provider)

    events = list(
        service.stream_generate_document(
            "desc", {"brand": "x"}, [], selected_palette=selected_palette
        )
    )

    state = [v for k, v in events if k == "done"][0].state
    assert state["styles"]["palette"] == {
        "id": "custom-mi-marca",
        "name": "Mi marca",
        "source": "custom",
    }
    assert state["styles"]["variables"] == selected_palette["variables"]
