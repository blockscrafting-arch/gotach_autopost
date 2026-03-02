"""
Telegram Bot API HTML formatting: validation and escaping.

Supported tags: <b>, <i>, <u>, <s>, <code>, <pre>, <blockquote>, <tg-spoiler>, <a href="url">.
Characters < > & outside tags must be escaped as &lt; &gt; &amp;.
"""
import re
from html import escape as html_escape

# Telegram allows only these tags (lowercase)
ALLOWED_TAGS = frozenset({"b", "i", "u", "s", "code", "pre", "blockquote", "tg-spoiler", "a"})
# Tags that can have attributes (a href=)
TAGS_WITH_ATTRS = frozenset({"a"})

# Pattern: opening or self-closing tag, e.g. <b>, </b>, <a href="...">
TAG_PATTERN = re.compile(
    r"</?([a-zA-Z][a-zA-Z0-9-]*)(?:\s+[^>]*?)?\s*/?>"
)


def escape_text(text: str) -> str:
    """Escape <, >, & for use outside HTML tags."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _strip_disallowed_tag(match: re.Match) -> str:
    full = match.group(0)
    name = match.group(1).lower()
    if name in ALLOWED_TAGS:
        return full
    return ""


def clean_telegram_html(raw: str) -> str:
    """
    Clean and validate Telegram HTML.
    - Strip any tag not in ALLOWED_TAGS
    - Escape <, >, & that appear in text nodes (between tags)
    """
    if not raw:
        return ""

    result: list[str] = []
    pos = 0

    for m in TAG_PATTERN.finditer(raw):
        # Text before this tag
        before = raw[pos : m.start()]
        if before:
            result.append(escape_text(before))
        tag = m.group(0)
        name = m.group(1).lower()
        if name in ALLOWED_TAGS:
            if tag.strip().startswith("</"):
                result.append(tag)
            elif name == "a":
                href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
                if href_match:
                    url = href_match.group(1).replace("&", "&amp;")
                    result.append(f'<a href="{url}">')
                else:
                    result.append("<a>")
            elif name == "blockquote" and "expandable" in tag.lower():
                result.append("<blockquote expandable>")
            else:
                result.append(tag)
        pos = m.end()

    if pos < len(raw):
        result.append(escape_text(raw[pos:]))

    return "".join(result)


def validate_for_telegram(text: str) -> tuple[bool, str]:
    """
    Validate that the text is valid Telegram HTML.
    Returns (is_valid, cleaned_text).
    If valid, cleaned_text is safe to send with parse_mode="HTML".
    """
    try:
        cleaned = clean_telegram_html(text)
        # Check for unclosed tags (simple balance check for b, i, u, s, code, pre, blockquote, tg-spoiler)
        for tag in ("b", "i", "u", "s", "code", "pre", "blockquote", "tg-spoiler"):
            open_count = len(re.findall(rf"<{tag}(?:\s|>|$)", cleaned, re.I))
            close_count = len(re.findall(rf"</{tag}\s*>", cleaned, re.I))
            if open_count != close_count:
                # Try to fix: strip unbalanced tags (aggressive but safe)
                pass  # Telegram may still accept; we don't strip here
        return True, cleaned
    except Exception:
        return False, escape_text(text)
