"""Cloud quick-answer tool — delegate simple queries to a fast Gemini model."""

from __future__ import annotations

import logging

from pantheon.config import settings
from pantheon.core.tools import tool

log = logging.getLogger(__name__)


@tool(
    "ask_flash",
    "Ask Gemini Flash for a quick answer — faster and cheaper for simple questions",
    {"prompt": {"type": "string", "description": "The prompt to send to the fast model"}},
)
async def ask_flash(prompt: str) -> str:
    """Send a prompt to Gemini Flash for a quick response."""
    if not settings.google_ai_api_key:
        return "Google AI API key not configured. Set GOOGLE_AI_API_KEY in .env."

    try:
        from google import genai

        client = genai.Client(api_key=settings.google_ai_api_key)
        response = client.models.generate_content(
            model=settings.cloud_fast_model,
            contents=prompt,
        )
        return response.text or "(empty response from Flash model)"

    except ImportError:
        return "google-genai package not installed. Run: pip install google-genai"
    except Exception as e:
        log.error("Flash query failed: %s", e)
        return f"Flash request failed: {e}"
