import json
from types import SimpleNamespace

import pytest

from apps.ai_assistant.providers import (
    AIProviderError,
    AIProviderTimeout,
    AnthropicMessagesProvider,
    FakeAIProvider,
    OpenCodeZenProvider,
    _build_anthropic_messages,
    _build_messages,
    build_provider,
)


def test_build_messages_injects_history_in_order():
    history = [
        {"role": "user", "content": "Cambia el título"},
        {"role": "assistant", "content": "Listo"},
    ]
    messages = _build_messages("SYS", history, {"instruction": "ahora en mayúsculas"})
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == "SYS"
    # Malformed / non user-assistant turns are dropped.
    dirty = _build_messages("SYS", [{"role": "system", "content": "x"}, "nope"], {})
    assert [m["role"] for m in dirty] == ["system", "user"]


def test_build_provider_returns_opencode_zen_when_configured(settings):
    settings.AI_PROVIDER = "opencode_zen"
    settings.OPENCODE_ZEN_API_KEY = "zen-key"
    settings.OPENCODE_ZEN_MODEL = "gpt-4o-mini"
    settings.OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/go/v1"

    provider = build_provider(settings)

    assert isinstance(provider, OpenCodeZenProvider)
    assert provider.api_key == "zen-key"
    assert provider.model == "gpt-4o-mini"
    assert provider.base_url == "https://opencode.ai/zen/go/v1"


def test_build_provider_routes_anthropic_style_models(settings):
    # MiniMax/Qwen3.7 models speak the Anthropic Messages API on opencode.ai,
    # not OpenAI chat/completions — build_provider must route by model name.
    settings.AI_PROVIDER = "opencode_zen"
    settings.OPENCODE_ZEN_API_KEY = "zen-key"
    settings.OPENCODE_ZEN_MODEL = "minimax-m3"
    settings.OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/go/v1"

    provider = build_provider(settings)

    assert isinstance(provider, AnthropicMessagesProvider)
    assert provider.model == "minimax-m3"
    # The Anthropic SDK appends /v1/messages itself — the /v1 must be stripped.
    assert provider.base_url == "https://opencode.ai/zen/go"


def test_build_provider_model_override_also_routes_by_model(settings):
    settings.AI_PROVIDER = "opencode_zen"
    settings.OPENCODE_ZEN_API_KEY = "zen-key"
    settings.OPENCODE_ZEN_MODEL = "mimo-v2.5"  # default is openai-compatible
    settings.OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/go/v1"

    provider = build_provider(settings, model="qwen3.7-max")

    assert isinstance(provider, AnthropicMessagesProvider)
    assert provider.model == "qwen3.7-max"


def test_build_provider_falls_back_to_fake_without_key(settings):
    settings.AI_PROVIDER = "opencode_zen"
    settings.OPENCODE_ZEN_API_KEY = ""

    provider = build_provider(settings)

    assert isinstance(provider, FakeAIProvider)


def _make_response(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _provider():
    return OpenCodeZenProvider(
        api_key="zen-key",
        model="gpt-4o-mini",
        base_url="https://opencode.ai/zen/go/v1",
        timeout=30,
        max_output_tokens=8000,
    )


def test_generate_returns_parsed_dict(mocker):
    provider = _provider()
    expected = {"summary": "s", "operations": [{"action": "set_text", "path": [0], "value": "x"}]}
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = _make_response(
        json.dumps(expected, ensure_ascii=False)
    )
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    result = provider.generate(system_prompt="sys", payload={"a": 1}, schema={})

    assert result == {**expected, "reasoning": None}
    fake_client.chat.completions.create.assert_called_once()
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["messages"][0] == {"role": "system", "content": "sys"}
    assert kwargs["response_format"]["type"] == "json_schema"


def test_generate_repairs_truncated_json(mocker):
    # Long generations sometimes get cut off mid-object (missing closing
    # braces/quotes) — this must be salvaged instead of failing outright.
    provider = _provider()
    truncated = '{"summary": "s", "operations": [{"action": "set_text", "path": [0'
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = _make_response(truncated)
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    result = provider.generate(system_prompt="sys", payload={"a": 1}, schema={})

    assert result["summary"] == "s"


def test_generate_extracts_think_block_as_reasoning(mocker):
    provider = _provider()
    payload = {"summary": "s", "operations": []}
    raw_text = f"<think>Voy a agregar un hero.</think>{json.dumps(payload)}"
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = _make_response(raw_text)
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    result = provider.generate(system_prompt="sys", payload={"a": 1}, schema={})

    assert result["reasoning"] == "Voy a agregar un hero."
    assert result["summary"] == "s"


def test_generate_empty_content_raises_provider_error(mocker):
    provider = _provider()
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = _make_response("")
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    with pytest.raises(AIProviderError):
        provider.generate(system_prompt="sys", payload={}, schema={})


def test_generate_invalid_json_raises_provider_error(mocker):
    provider = _provider()
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = _make_response("not json")
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    with pytest.raises(AIProviderError):
        provider.generate(system_prompt="sys", payload={}, schema={})


def test_generate_timeout_maps_to_ai_provider_timeout(mocker):
    from openai import APITimeoutError

    provider = _provider()
    provider.max_retries = 0
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.side_effect = APITimeoutError(request=mocker.Mock())
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    with pytest.raises(AIProviderTimeout):
        provider.generate(system_prompt="sys", payload={}, schema={})


def test_generate_connection_error_maps_to_ai_provider_error(mocker):
    from openai import APIConnectionError

    provider = _provider()
    provider.max_retries = 0
    fake_client = mocker.Mock()
    fake_client.chat.completions.create.side_effect = APIConnectionError(request=mocker.Mock())
    mocker.patch.object(OpenCodeZenProvider, "_client", return_value=fake_client)

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate(system_prompt="sys", payload={}, schema={})
    assert exc_info.type is AIProviderError


# --- AnthropicMessagesProvider ------------------------------------------------


def test_build_anthropic_messages_has_no_system_role():
    history = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola!"}]
    messages = _build_anthropic_messages(history, {"a": 1})
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]


def _anthropic_provider():
    return AnthropicMessagesProvider(
        api_key="zen-key",
        model="minimax-m3",
        base_url="https://opencode.ai/zen/go",
        timeout=30,
        max_output_tokens=8000,
    )


def _anthropic_response(text: str):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


def test_anthropic_generate_returns_parsed_dict(mocker):
    provider = _anthropic_provider()
    expected = {"summary": "s", "operations": []}
    fake_client = mocker.Mock()
    fake_client.messages.create.return_value = _anthropic_response(json.dumps(expected))
    mocker.patch.object(AnthropicMessagesProvider, "_client", return_value=fake_client)

    result = provider.generate(system_prompt="sys", payload={"a": 1}, schema={})

    assert result == {**expected, "reasoning": None}
    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["model"] == "minimax-m3"
    assert kwargs["system"] == "sys"
    assert kwargs["max_tokens"] == 8000
    assert all(m["role"] != "system" for m in kwargs["messages"])


def test_anthropic_generate_extracts_think_block(mocker):
    provider = _anthropic_provider()
    payload = {"summary": "s", "operations": []}
    raw_text = f"<think>Pensando.</think>{json.dumps(payload)}"
    fake_client = mocker.Mock()
    fake_client.messages.create.return_value = _anthropic_response(raw_text)
    mocker.patch.object(AnthropicMessagesProvider, "_client", return_value=fake_client)

    result = provider.generate(system_prompt="sys", payload={"a": 1}, schema={})

    assert result["reasoning"] == "Pensando."


def test_anthropic_generate_empty_content_raises_provider_error(mocker):
    provider = _anthropic_provider()
    fake_client = mocker.Mock()
    fake_client.messages.create.return_value = _anthropic_response("")
    mocker.patch.object(AnthropicMessagesProvider, "_client", return_value=fake_client)

    with pytest.raises(AIProviderError):
        provider.generate(system_prompt="sys", payload={}, schema={})


def test_anthropic_generate_timeout_maps_to_ai_provider_timeout(mocker):
    from anthropic import APITimeoutError

    provider = _anthropic_provider()
    provider.max_retries = 0
    fake_client = mocker.Mock()
    fake_client.messages.create.side_effect = APITimeoutError(request=mocker.Mock())
    mocker.patch.object(AnthropicMessagesProvider, "_client", return_value=fake_client)

    with pytest.raises(AIProviderTimeout):
        provider.generate(system_prompt="sys", payload={}, schema={})
