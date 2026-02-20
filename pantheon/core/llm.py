"""Gemini LLM client — chat and tool calling via Google AI Studio API."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from google import genai
from google.genai import types

from pantheon.config import settings

log = logging.getLogger(__name__)

# Module-level client — reuses connection pool across calls
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini client."""
    global _client
    if _client is None:
        if not settings.google_ai_api_key:
            raise RuntimeError(
                "GOOGLE_AI_API_KEY not set. Add it to your .env file."
            )
        _client = genai.Client(api_key=settings.google_ai_api_key)
    return _client


async def chat(
    messages: list[types.Content],
    system_instruction: str = "",
    tools: list[dict[str, Any]] | None = None,
) -> types.GenerateContentResponse:
    """Send a chat completion request to Gemini.

    Args:
        messages: Conversation history as Gemini Content objects.
        system_instruction: System prompt text.
        tools: Tool declarations (function schemas) in Gemini format.

    Returns:
        The full GenerateContentResponse.
    """
    import asyncio
    import time

    client = _get_client()

    config_kwargs: dict[str, Any] = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if tools:
        config_kwargs["tools"] = [types.Tool(function_declarations=tools)]

    config = types.GenerateContentConfig(**config_kwargs)

    log.info(
        "Gemini request: %d messages, %d tools",
        len(messages),
        len(tools) if tools else 0,
    )
    t0 = time.monotonic()

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.google_ai_model,
            contents=messages,
            config=config,
        )
        elapsed = time.monotonic() - t0
        log.info("Gemini response in %.1fs", elapsed)
        return response

    except Exception as e:
        elapsed = time.monotonic() - t0
        log.error("Gemini request failed after %.1fs: %s", elapsed, e)
        raise


async def stream_chat(
    messages: list[types.Content],
    system_instruction: str = "",
) -> AsyncIterator[str]:
    """Stream a chat response from Gemini, yielding content chunks."""
    import asyncio

    client = _get_client()

    config_kwargs: dict[str, Any] = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    config = types.GenerateContentConfig(**config_kwargs)

    # Run the streaming call in a thread since the SDK is synchronous
    def _stream():
        return client.models.generate_content_stream(
            model=settings.google_ai_model,
            contents=messages,
            config=config,
        )

    stream = await asyncio.to_thread(_stream)
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def has_tool_calls(response: types.GenerateContentResponse) -> bool:
    """Check if the response contains function calls."""
    if not response.candidates:
        return False
    parts = response.candidates[0].content.parts
    return any(p.function_call and p.function_call.name for p in parts)


def extract_tool_calls(
    response: types.GenerateContentResponse,
) -> list[types.FunctionCall]:
    """Extract function calls from a Gemini response."""
    if not response.candidates:
        return []
    parts = response.candidates[0].content.parts
    return [p.function_call for p in parts if p.function_call and p.function_call.name]


def extract_content(response: types.GenerateContentResponse) -> str:
    """Extract the text content from a Gemini response."""
    try:
        return response.text or ""
    except Exception:
        # response.text can raise if there's no text part
        return ""


def get_model_response_content(
    response: types.GenerateContentResponse,
) -> types.Content:
    """Get the full Content object from the model's response.

    Must be appended to conversation history as-is to preserve
    thought signatures and function call references.
    """
    return response.candidates[0].content


def build_function_response_content(
    tool_name: str,
    result: str,
) -> types.Content:
    """Build a Content object with a function response to feed back to the model.

    Per Gemini API convention, function responses are sent as role="user".
    """
    part = types.Part.from_function_response(
        name=tool_name,
        response={"result": result},
    )
    return types.Content(role="user", parts=[part])


def build_user_content(text: str) -> types.Content:
    """Build a user message Content object."""
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def build_model_content(text: str) -> types.Content:
    """Build a model message Content object (for conversation history)."""
    return types.Content(role="model", parts=[types.Part.from_text(text=text)])
