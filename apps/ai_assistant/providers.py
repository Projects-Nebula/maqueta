"""Pluggable AI providers.

The service depends on the ``AIProvider`` interface, so the OpenAI provider can
be swapped for the deterministic fake in tests and offline development.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod

# Reasoning models (e.g. MiniMax) prefix a <think>...</think> block; some
# providers wrap JSON in Markdown fences. Strip reasoning, then decode the first
# JSON object, ignoring any surrounding prose.
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def _extract_reasoning(text: str) -> str | None:
    """Pull the model's <think> block out, if it emitted one, for display."""
    match = _THINK_RE.search(text)
    if not match:
        return None
    reasoning = match.group(1).strip()
    return reasoning or None


def _extract_json_object(text: str) -> dict:
    cleaned = _THINK_RE.sub("", text)
    start = cleaned.find("{")
    if start == -1:
        raise AIResponseFormatError("AI response contained no JSON object")
    candidate = cleaned[start:]
    try:
        obj, _ = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError:
        # Some models (long generations especially) drop a comma or leave a
        # string/object unterminated. Try to salvage it before giving up —
        # this is the difference between "retry the whole generation" and
        # "use what we already got" for an otherwise-complete response.
        obj = _repair_json_object(candidate)
    if not isinstance(obj, dict):
        raise AIResponseFormatError("AI response was not a JSON object")
    return obj


def _repair_json_object(candidate: str):
    from json_repair import repair_json  # imported lazily so tests need no install

    try:
        repaired = repair_json(candidate, return_objects=True)
    except Exception as exc:
        raise AIResponseFormatError("AI response was not valid JSON") from exc
    if not isinstance(repaired, dict) or not repaired:
        raise AIResponseFormatError("AI response was not valid JSON")
    return repaired


def _build_messages(system_prompt: str, history, payload: dict) -> list:
    """system prompt + prior chat turns + the current turn's JSON payload.

    History gives the assistant conversational context ("ahora hazlo más
    grande"). It is untrusted text, already bounded by the serializer; here we
    only keep well-formed user/assistant turns.
    """
    messages = [{"role": "system", "content": system_prompt}]
    for item in history or []:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    return messages


def _build_anthropic_messages(history, payload: dict) -> list:
    """Same as _build_messages, minus the system turn — the Anthropic
    Messages API takes ``system`` as its own top-level request field, not a
    message with role "system"."""
    messages = []
    for item in history or []:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    return messages


class AIProviderError(Exception):
    """Non-retryable provider failure (bad output, auth, etc.)."""


class AIProviderTimeout(AIProviderError):
    """The provider took too long to respond."""


class AIResponseFormatError(AIProviderError):
    """The model returned content that is not the expected JSON object.

    Reasoning models occasionally emit malformed JSON on large generations;
    this is worth a bounded retry (unlike auth or schema-shape errors).
    """


class AIProvider(ABC):
    @abstractmethod
    def generate(
        self, *, system_prompt: str, payload: dict, schema: dict, history: list | None = None
    ) -> dict:
        """Return the parsed JSON object produced by the model."""

    def stream_generate(
        self, *, system_prompt: str, payload: dict, schema: dict, history: list | None = None
    ):
        """Yield ("reasoning", text) chunks, then a final ("done", dict).

        Default for providers with no real streaming support: run the
        blocking call once and replay its reasoning as a single chunk.
        """
        result = self.generate(
            system_prompt=system_prompt, payload=payload, schema=schema, history=history
        )
        reasoning = result.get("reasoning") if isinstance(result, dict) else None
        if reasoning:
            yield "reasoning", reasoning
        yield "done", result


class FakeAIProvider(AIProvider):
    """Deterministic provider for tests and no-API-key development.

    It makes a single, obviously-safe edit: it rewrites the first text node of
    the selected element (or sets a highlight class when there is no text).
    """

    def generate(self, *, system_prompt, payload, schema, history=None):
        selected_path = payload.get("selected_path") or []
        node = payload.get("selected_node") or {}
        instruction = payload.get("instruction", "")

        text_index = _first_text_child_index(node)
        if text_index is not None:
            return {
                "summary": f"Texto actualizado según: {instruction}"[:200],
                "operations": [
                    {
                        "action": "set_text",
                        "path": [*selected_path, text_index],
                        "value": f"{_first_text_value(node)} ✦",
                    }
                ],
            }

        existing = node.get("attributes", {}).get("class") or []
        if isinstance(existing, str):
            existing = existing.split()
        return {
            "summary": f"Clase destacada agregada según: {instruction}"[:200],
            "operations": [
                {
                    "action": "set_attribute",
                    "path": selected_path,
                    "attribute": "class",
                    "value": [*existing, "bg-yellow-100"],
                }
            ],
        }


class OpenAIProvider(AIProvider):
    """OpenAI Responses API provider with structured output and bounded retries."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: int,
        max_output_tokens: int,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries

    def _client(self):
        from openai import OpenAI  # imported lazily so tests need no openai install

        # max_retries=0: retries are handled by our own bounded loop below —
        # the SDK's own internal retries would stack on top of it and turn a
        # single slow request into several minutes of retry-of-retries.
        return OpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=0)

    def generate(self, *, system_prompt, payload, schema, history=None):
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        client = self._client()
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.responses.create(
                    model=self.model,
                    input=_build_messages(system_prompt, history, payload),
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "editor_operations",
                            "schema": schema,
                        }
                    },
                    max_output_tokens=self.max_output_tokens,
                )
                return self._parse(response)
            except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
                # Only transient errors are retried, with simple backoff.
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if isinstance(exc, APITimeoutError):
                    raise AIProviderTimeout("AI provider timed out") from exc
                raise AIProviderError("AI provider unavailable") from exc
            except Exception as exc:  # bad output / auth / anything else: do not retry
                raise AIProviderError(str(exc)) from exc
        raise AIProviderError(str(last_exc))

    @staticmethod
    def _parse(response):
        text = getattr(response, "output_text", None)
        if not text:
            raise AIProviderError("empty AI response")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIProviderError("AI response was not valid JSON") from exc


class OpenCodeZenProvider(AIProvider):
    """OpenCode Zen Chat Completions provider (OpenAI-compatible) with bounded retries."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int,
        max_output_tokens: int,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries

    def _client(self):
        from openai import OpenAI  # imported lazily so tests need no openai install

        # max_retries=0: retries are handled by our own bounded loop below —
        # the SDK's own internal retries would stack on top of it and turn a
        # single slow request into several minutes of retry-of-retries.
        return OpenAI(
            api_key=self.api_key, base_url=self.base_url, timeout=self.timeout, max_retries=0
        )

    def _stream_client(self):
        import httpx
        from openai import OpenAI

        # httpx's "read" timeout is per-chunk inactivity, not a total-request
        # cap — so as long as the model keeps emitting reasoning tokens, no
        # matter how slowly, the request must not time out mid-stream. Only
        # connect/write/pool stay bounded, to still fail fast on real
        # connectivity problems (server unreachable, etc).
        timeout = httpx.Timeout(self.timeout, read=max(self.timeout, 300))
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout, max_retries=0)

    def generate(self, *, system_prompt, payload, schema, history=None):
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        client = self._client()
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=_build_messages(system_prompt, history, payload),
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "editor_operations",
                            "schema": schema,
                            "strict": False,
                        },
                    },
                    max_tokens=self.max_output_tokens,
                )
                return self._parse(response)
            except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
                # Only transient errors are retried, with simple backoff.
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if isinstance(exc, APITimeoutError):
                    raise AIProviderTimeout("AI provider timed out") from exc
                raise AIProviderError("AI provider unavailable") from exc
            except AIResponseFormatError as exc:
                # Reasoning models occasionally emit malformed JSON; retry a
                # bounded number of times, then give up (never loop forever).
                last_exc = exc
                if attempt < self.max_retries:
                    continue
                raise
            except Exception as exc:  # auth / anything else: do not retry
                raise AIProviderError(str(exc)) from exc
        raise AIProviderError(str(last_exc))

    @staticmethod
    def _parse(response):
        choices = getattr(response, "choices", None)
        text = choices[0].message.content if choices else None
        if not text:
            raise AIResponseFormatError("empty AI response")
        # Tolerant: strips <think> blocks / Markdown fences / prose around JSON.
        obj = _extract_json_object(text)
        obj["reasoning"] = _extract_reasoning(text)
        return obj

    # ponytail: retry bookkeeping duplicates generate() above — streaming
    # accumulates text incrementally instead of parsing one final response,
    # so sharing a helper would cost more than the ~20 duplicated lines.
    def stream_generate(self, *, system_prompt, payload, schema, history=None):
        """Yield ("reasoning", delta) as the model's <think> block arrives,
        then a final ("done", parsed_dict) once the stream completes."""
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        client = self._stream_client()
        last_exc = None
        for attempt in range(self.max_retries + 1):
            buffer = ""
            emitted = 0
            try:
                stream = client.chat.completions.create(
                    model=self.model,
                    messages=_build_messages(system_prompt, history, payload),
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "editor_operations",
                            "schema": schema,
                            "strict": False,
                        },
                    },
                    max_tokens=self.max_output_tokens,
                    stream=True,
                )
                for chunk in stream:
                    choices = getattr(chunk, "choices", None)
                    delta = choices[0].delta.content if choices else None
                    if not delta:
                        continue
                    buffer += delta
                    lowered = buffer.lower()
                    start = lowered.find("<think>")
                    if start == -1:
                        continue
                    content_start = start + len("<think>")
                    end = lowered.find("</think>", content_start)
                    visible_end = end if end != -1 else len(buffer)
                    visible = buffer[content_start:visible_end]
                    if len(visible) > emitted:
                        yield "reasoning", visible[emitted:]
                        emitted = len(visible)
                if not buffer:
                    raise AIResponseFormatError("empty AI response")
                obj = _extract_json_object(buffer)
                obj["reasoning"] = _extract_reasoning(buffer)
                yield "done", obj
                return
            except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if isinstance(exc, APITimeoutError):
                    raise AIProviderTimeout("AI provider timed out") from exc
                raise AIProviderError("AI provider unavailable") from exc
            except AIResponseFormatError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    continue
                raise
            except Exception as exc:  # auth / anything else: do not retry
                raise AIProviderError(str(exc)) from exc
        raise AIProviderError(str(last_exc))


class AnthropicMessagesProvider(AIProvider):
    """opencode_zen models that speak the Anthropic Messages API instead of
    OpenAI chat/completions — per opencode.ai's model table, MiniMax and the
    Qwen3.7 family need POST {base_url}/v1/messages with the Anthropic wire
    format (system as a top-level field, no system-role message, max_tokens
    required), not /v1/chat/completions. Calling the wrong shape is what
    caused intermittent malformed-JSON failures on long MiniMax generations
    — the gateway was translating between protocols under the hood.

    These are non-Claude models proxied through an Anthropic-shaped
    endpoint, not Claude's native extended-thinking feature, so reasoning
    still arrives as a <think> tag inside the plain text content — <think>
    extraction is identical to OpenCodeZenProvider; only the wire protocol
    differs.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int,
        max_output_tokens: int,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries

    def _client(self):
        from anthropic import Anthropic  # imported lazily so tests need no anthropic install

        # max_retries=0: retries are handled by our own bounded loop below —
        # the SDK's own internal retries would stack on top of it and turn a
        # single slow request into several minutes of retry-of-retries.
        return Anthropic(
            api_key=self.api_key, base_url=self.base_url, timeout=self.timeout, max_retries=0
        )

    def _stream_client(self):
        import httpx
        from anthropic import Anthropic

        # Same reasoning as OpenCodeZenProvider._stream_client: httpx's read
        # timeout is per-chunk inactivity, not a total-request cap, so a
        # slow-but-still-streaming response must not time out mid-generation.
        timeout = httpx.Timeout(self.timeout, read=max(self.timeout, 300))
        return Anthropic(
            api_key=self.api_key, base_url=self.base_url, timeout=timeout, max_retries=0
        )

    def generate(self, *, system_prompt, payload, schema, history=None):
        from anthropic import APIConnectionError, APITimeoutError, RateLimitError

        client = self._client()
        messages = _build_anthropic_messages(history, payload)
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=self.max_output_tokens,
                )
                return self._parse(response)
            except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if isinstance(exc, APITimeoutError):
                    raise AIProviderTimeout("AI provider timed out") from exc
                raise AIProviderError("AI provider unavailable") from exc
            except AIResponseFormatError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    continue
                raise
            except Exception as exc:  # auth / anything else: do not retry
                raise AIProviderError(str(exc)) from exc
        raise AIProviderError(str(last_exc))

    @staticmethod
    def _parse(response):
        blocks = getattr(response, "content", None) or []
        text = "".join(b.text for b in blocks if getattr(b, "type", None) == "text")
        if not text:
            raise AIResponseFormatError("empty AI response")
        obj = _extract_json_object(text)
        obj["reasoning"] = _extract_reasoning(text)
        return obj

    # ponytail: retry bookkeeping duplicates generate() above — same
    # tradeoff already accepted for OpenCodeZenProvider's stream_generate.
    def stream_generate(self, *, system_prompt, payload, schema, history=None):
        """Yield ("reasoning", delta) as the model's <think> block arrives,
        then a final ("done", parsed_dict) once the stream completes."""
        from anthropic import APIConnectionError, APITimeoutError, RateLimitError

        client = self._stream_client()
        messages = _build_anthropic_messages(history, payload)
        last_exc = None
        for attempt in range(self.max_retries + 1):
            buffer = ""
            emitted = 0
            try:
                with client.messages.stream(
                    model=self.model,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=self.max_output_tokens,
                ) as stream:
                    for delta in stream.text_stream:
                        if not delta:
                            continue
                        buffer += delta
                        lowered = buffer.lower()
                        start = lowered.find("<think>")
                        if start == -1:
                            continue
                        content_start = start + len("<think>")
                        end = lowered.find("</think>", content_start)
                        visible_end = end if end != -1 else len(buffer)
                        visible = buffer[content_start:visible_end]
                        if len(visible) > emitted:
                            yield "reasoning", visible[emitted:]
                            emitted = len(visible)
                if not buffer:
                    raise AIResponseFormatError("empty AI response")
                obj = _extract_json_object(buffer)
                obj["reasoning"] = _extract_reasoning(buffer)
                yield "done", obj
                return
            except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if isinstance(exc, APITimeoutError):
                    raise AIProviderTimeout("AI provider timed out") from exc
                raise AIProviderError("AI provider unavailable") from exc
            except AIResponseFormatError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    continue
                raise
            except Exception as exc:  # auth / anything else: do not retry
                raise AIProviderError(str(exc)) from exc
        raise AIProviderError(str(last_exc))


def _first_text_child_index(node):
    for index, child in enumerate(node.get("children", []) or []):
        if isinstance(child, dict) and child.get("type") == "text":
            return index
    return None


def _first_text_value(node):
    index = _first_text_child_index(node)
    if index is None:
        return ""
    return node["children"][index].get("value", "")


# opencode.ai routes these model IDs through the Anthropic Messages API
# (/v1/messages) rather than OpenAI chat/completions — per their published
# model table (Grok/GLM/Kimi/DeepSeek/MiMo are openai-compatible; MiniMax and
# Qwen3.7 are anthropic-compatible). Calling the wrong shape produces
# intermittent malformed output on long generations, not a clean error.
OPENCODE_ZEN_ANTHROPIC_MODELS = {
    "minimax-m3",
    "minimax-m2.7",
    "minimax-m2.5",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
}


def build_provider(settings, *, model: str | None = None) -> AIProvider:
    """Factory selecting the provider from Django settings.

    ``model`` overrides the configured model for this instance only — lets a
    call site use a different model on the same provider/credentials (e.g. a
    conversational model for chat-style calls vs. a stricter one for heavy
    structured-JSON generation; see WizardAIService).
    """
    provider = getattr(settings, "AI_PROVIDER", "fake")
    if provider == "openai" and settings.OPENAI_API_KEY:
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=model or settings.AI_MODEL,
            timeout=settings.AI_REQUEST_TIMEOUT,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
        )
    if provider == "opencode_zen" and settings.OPENCODE_ZEN_API_KEY:
        chosen_model = model or settings.OPENCODE_ZEN_MODEL
        if chosen_model in OPENCODE_ZEN_ANTHROPIC_MODELS:
            return AnthropicMessagesProvider(
                api_key=settings.OPENCODE_ZEN_API_KEY,
                model=chosen_model,
                # The Anthropic SDK appends /v1/messages itself — strip the
                # /v1 already present in the OpenAI-shaped base URL so the
                # two don't compose into /v1/v1/messages.
                base_url=settings.OPENCODE_ZEN_BASE_URL.removesuffix("/v1"),
                timeout=settings.AI_REQUEST_TIMEOUT,
                max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            )
        return OpenCodeZenProvider(
            api_key=settings.OPENCODE_ZEN_API_KEY,
            model=chosen_model,
            base_url=settings.OPENCODE_ZEN_BASE_URL,
            timeout=settings.AI_REQUEST_TIMEOUT,
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
        )
    return FakeAIProvider()
