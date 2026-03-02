# -*- coding: utf-8 -*-
"""Custom function declarations for Gemini (get_current_datetime, get_post_stats)."""

from datetime import datetime, timezone

# Function declarations in OpenAPI-style for Gemini API
GET_CURRENT_DATETIME_DECL = {
    "name": "get_current_datetime",
    "description": "Возвращает текущие дату и время (UTC и московское). Используй для контекста поста: 'сегодня', 'на этой неделе', актуальные события.",
    "parameters": {
        "type": "object",
        "properties": {
            "timezone_name": {
                "type": "string",
                "description": "Часовой пояс, например Europe/Moscow или UTC",
            }
        },
    },
}

GET_POST_STATS_DECL = {
    "name": "get_post_stats",
    "description": "Подсчитывает число слов и символов в тексте поста. Используй чтобы держать длину поста в диапазоне 150-350 слов.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Текст поста (можно с HTML-тегами)",
            }
        },
        "required": ["text"],
    },
}


def execute_get_current_datetime(timezone_name: str | None = None) -> dict:
    """Execute get_current_datetime tool."""
    tz = timezone.utc
    if timezone_name and timezone_name.lower() != "utc":
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone_name)
        except Exception:
            pass
    now = datetime.now(tz)
    return {
        "datetime_utc": now.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": now.strftime("%A"),
    }


def execute_get_post_stats(text: str) -> dict:
    """Execute get_post_stats tool: strip HTML and count words/chars."""
    import re
    # Strip tags for word count
    stripped = re.sub(r"<[^>]+>", " ", text)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    words = len(stripped.split()) if stripped else 0
    return {
        "words": words,
        "characters": len(text),
        "characters_no_html": len(stripped),
    }


def execute_tool(name: str, args: dict) -> dict:
    """Execute a tool by name and return result dict."""
    if name == "get_current_datetime":
        return execute_get_current_datetime(args.get("timezone_name"))
    if name == "get_post_stats":
        return execute_get_post_stats(args.get("text", ""))
    return {"error": f"Unknown tool: {name}"}
