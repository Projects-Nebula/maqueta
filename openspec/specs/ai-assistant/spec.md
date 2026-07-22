# Capability: ai-assistant

Turns a natural-language instruction plus a selected node into validated,
structured edit operations. Code: `apps/ai_assistant/`.
Endpoint: `POST /api/ai/editor/transform/` (Django session + CSRF; login required).

## Requirement: Authenticated transform
The system SHALL require an authenticated session for the transform endpoint,
using the browser session cookie plus an `X-CSRFToken` header (no JWT/bearer).

#### Scenario: Anonymous
- WHEN an unauthenticated client calls the endpoint
- THEN respond 401/403

## Requirement: Bounded, sanitized input
The system SHALL reject untrusted input that exceeds limits or is unsafe before
calling the provider.

#### Scenario: Oversized payload
- WHEN the serialized request exceeds `AI_MAX_INPUT_CHARACTERS`
- THEN respond 400

#### Scenario: Unsafe selected node
- WHEN `selected_node` contains a forbidden tag (`script/iframe/object/embed/applet/base`),
  an `on*` attribute, `srcdoc`, or an unsafe URL scheme
- THEN respond 400

#### Scenario: Missing selection
- WHEN neither `selected_node` nor `global_mode` is provided
- THEN respond 400

#### Scenario: Only necessary context is sent
- WHEN a transform runs
- THEN only the selected node, nearby context, design variables, page summary,
  and instruction are sent to the provider (never the full document)

## Requirement: Operation protocol
The AI SHALL return only `{summary, operations}` where every operation is one of:
`set_text`, `set_attribute`, `remove_attribute`, `set_style_variable`,
`set_css_declaration`, `remove_css_declaration`, `add_node`, `replace_node`,
`duplicate_node`, `delete_node`, `move_node`, `add_section`.

#### Scenario: Server-side validation is authoritative
- WHEN operations are produced (by any provider)
- THEN each is validated: allowed action, integer non-negative paths, no node
  moved into itself, allowlisted tags/attributes/CSS, safe URLs, and count/size
  within `AI_MAX_OPERATIONS`
- AND any violation rejects the whole response (HTTP 422 `invalid_operations`)

## Requirement: Swappable provider
The system SHALL depend on an `AIProvider` interface with these implementations,
selected by `AI_PROVIDER`:
- `FakeAIProvider` — tests/offline, no API key.
- `OpenAIProvider` — OpenAI Responses API with JSON schema, timeout, and retries
  limited to transient errors.
- `OpenCodeZenProvider` — OpenCode Zen OpenAI-compatible Chat Completions
  endpoint (`OPENCODE_ZEN_BASE_URL`), flat-price subscription key held
  server-side; same timeout/retry discipline.

#### Scenario: Offline default
- WHEN `OPENAI_API_KEY` is empty
- THEN `AI_PROVIDER` defaults to `fake` and the flow works without network

#### Scenario: Errors do not leak internals
- WHEN the provider times out → respond 504 `{"error": "ai_timeout"}`
- WHEN the provider errors → respond 502 `{"error": "ai_unavailable"}` with no internal detail

## Requirement: Configurable model
The model SHALL come from `AI_MODEL` (never hardcoded across files), with
`AI_REQUEST_TIMEOUT`, `AI_MAX_OPERATIONS`, `AI_MAX_INPUT_CHARACTERS` configurable.
