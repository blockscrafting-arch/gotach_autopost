# -*- coding: utf-8 -*-
"""OpenRouter API fallback when Gemini keys are unavailable."""

from __future__ import annotations

import httpx
from loguru import logger

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Fallback model if Gemini 3 not on OpenRouter
DEFAULT_MODEL = "google/gemini-2.0-flash-001"


def generate_post(
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
    *,
    timeout: float = 120.0,
) -> str:
    """
    Generate a post via OpenRouter chat completions API.
    model: e.g. google/gemini-2.0-flash-001 or google/gemini-3-flash (when available).
    """
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vladexecute/autopost-bot",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        raise

    choice = data.get("choices")
    if not choice:
        logger.warning("OpenRouter returned no choices")
        return ""

    message = choice[0].get("message", {})
    content = message.get("content") or message.get("text", "")
    return content.strip() if isinstance(content, str) else ""
