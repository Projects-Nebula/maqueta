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
            "attributes": {"class": ["page"]},
            "children": [{"type": "element", "tag": "h1", "attributes": {}, "children": []}],
        },
    },
    # Deliberately omitted here — the model does this under load; the service
    # must force them back in rather than fail the whole generation.
}

VALID_STYLES = {"variables": {}, "rules": [], "keyframes": []}


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
    assert state["styles"] == VALID_STYLES
