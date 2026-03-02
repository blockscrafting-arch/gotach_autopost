# -*- coding: utf-8 -*-
"""Multi-provider: Gemini Key1 -> Gemini Key2 -> OpenRouter."""

from __future__ import annotations

from loguru import logger

from autopost_bot.ai.gemini_client import generate_post as gemini_generate
from autopost_bot.ai.openrouter import generate_post as openrouter_generate


class AllProvidersFailedError(Exception):
    """All AI providers (Gemini keys + OpenRouter) failed."""


def generate_post(
    system_prompt: str,
    user_message: str,
    *,
    gemini_keys: list[str],
    openrouter_key: str | None,
    model: str = "gemini-3-flash-preview",
    openrouter_model: str | None = None,
) -> str:
    """
    Try Gemini with each key, then OpenRouter. Return first successful post text.
    Raises AllProvidersFailedError if all fail.
    """
    errors: list[str] = []

    for i, key in enumerate(gemini_keys):
        if not key:
            continue
        try:
            logger.info(f"Trying Gemini provider {i + 1}/{len(gemini_keys)}")
            text = gemini_generate(api_key=key, model=model, system_prompt=system_prompt, user_message=user_message)
            if text:
                return text
        except Exception as e:
            err = f"Gemini key {i + 1}: {e!s}"
            errors.append(err)
            logger.warning(err)
            continue

    if openrouter_key and openrouter_key.strip():
        fallback_model = openrouter_model or "google/gemini-3-flash-preview"
        try:
            logger.info("Trying OpenRouter fallback (model={})", fallback_model)
            text = openrouter_generate(
                api_key=openrouter_key.strip(),
                model=fallback_model,
                system_prompt=system_prompt,
                user_message=user_message,
            )
            if text:
                return text
        except Exception as e:
            errors.append(f"OpenRouter: {e!s}")
            logger.warning(f"OpenRouter failed: {e}")

    raise AllProvidersFailedError("; ".join(errors) if errors else "No providers configured")
