# -*- coding: utf-8 -*-
"""Gemini 3 Flash client with tools (Function Calling only; Google Search cannot be combined with custom tools per API)."""

from __future__ import annotations

from typing import Any

from loguru import logger

from autopost_bot.ai.tools import GET_CURRENT_DATETIME_DECL, GET_POST_STATS_DECL


def _get_genai_types():
    """Lazy import google.genai.types to avoid import errors if not installed."""
    try:
        from google import genai
        from google.genai import types
        return genai, types
    except ImportError as e:
        raise ImportError("Install google-genai: pip install google-genai") from e


def build_gemini_config(types: Any) -> Any:
    """Build GenerateContentConfig with Function Calling only (get_current_datetime, get_post_stats)."""
    return types.GenerateContentConfig(
        tools=[
            types.Tool(
                function_declarations=[
                    GET_CURRENT_DATETIME_DECL,
                    GET_POST_STATS_DECL,
                ]
            ),
        ],
    )


# Request timeout in ms (120 s) — Gemini sometimes needs more than 90s, then we fallback to next key
GEMINI_REQUEST_TIMEOUT_MS = 120_000


def generate_post(api_key: str, model: str, system_prompt: str, user_message: str) -> str:
    """
    Generate a post using Gemini 3 Flash.
    Returns the final post text (Telegram HTML).
    """
    genai, types = _get_genai_types()
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=GEMINI_REQUEST_TIMEOUT_MS),
    )
    base_config = build_gemini_config(types)
    config = types.GenerateContentConfig(
        tools=base_config.tools,
        system_instruction=system_prompt,
    )

    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=config,
    )

    if not response.candidates:
        logger.warning("Gemini returned no candidates")
        return ""

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        return ""

    text_parts = []
    for part in candidate.content.parts:
        if hasattr(part, "text") and part.text:
            text_parts.append(part.text)
    return "\n".join(text_parts).strip() if text_parts else ""
