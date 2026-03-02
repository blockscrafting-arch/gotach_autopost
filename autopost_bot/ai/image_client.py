# -*- coding: utf-8 -*-
"""Generate post image via Gemini 3.1 Flash Image (reference photos + post summary)."""

from __future__ import annotations

from loguru import logger

from autopost_bot.prompts.system_prompt import (
    IMAGE_GENERATION_SYSTEM_PROMPT,
    build_image_prompt,
)

# Request timeout in ms (90 s) so a hanging image API does not block the bot
IMAGE_REQUEST_TIMEOUT_MS = 90_000


def _get_genai_types():
    """Lazy import google.genai.types."""
    try:
        from google import genai
        from google.genai import types
        return genai, types
    except ImportError as e:
        raise ImportError("Install google-genai: pip install google-genai") from e


def generate_post_image(
    api_key: str,
    model: str,
    post_text_or_summary: str,
    reference_photo_bytes: list[tuple[bytes, str]],
) -> bytes | None:
    """
    Generate one meme/reference image for the post using Gemini 3.1 Flash Image.
    reference_photo_bytes: list of (data, mime_type) from get_reference_photo_bytes().
    Returns image bytes or None on failure/empty.
    """
    if not (post_text_or_summary or "").strip():
        logger.warning("Image generation skipped: empty post summary")
        return None
    genai_client, types = _get_genai_types()
    client = genai_client.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=IMAGE_REQUEST_TIMEOUT_MS),
    )

    # Build contents: reference images first, then text prompt
    parts: list = []
    for data, mime_type in reference_photo_bytes:
        parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))
    prompt = build_image_prompt(post_text_or_summary)
    parts.append(types.Part.from_text(text=prompt))

    config = types.GenerateContentConfig(
        response_modalities=[types.Modality.TEXT, types.Modality.IMAGE],
        image_config=types.ImageConfig(
            aspect_ratio="3:4",
            image_size="2K",
        ),
        thinking_config=types.ThinkingConfig(thinking_level="high"),
        tools=[types.Tool(google_search=types.GoogleSearch())],
        system_instruction=IMAGE_GENERATION_SYSTEM_PROMPT,
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=parts,
            config=config,
        )
    except Exception as e:
        logger.warning("Image generation request failed: {}", e)
        return None

    if not response.candidates:
        logger.warning("Image model returned no candidates")
        return None

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        return None

    for part in candidate.content.parts:
        if getattr(part, "inline_data", None) and part.inline_data:
            data = getattr(part.inline_data, "data", None) or getattr(
                part.inline_data, "image_bytes", None
            )
            if data:
                return data

    logger.warning("Image model response had no inline_data part")
    return None
