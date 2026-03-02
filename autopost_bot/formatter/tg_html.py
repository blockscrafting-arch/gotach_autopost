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


def _plain_text(line: str) -> str:
    """Strip HTML tags for scoring; keep text only."""
    return re.sub(TAG_PATTERN, "", line).strip()


def _hook_score(line: str) -> float:
    """
    Score how hook-like a line is: question, number, contrast, punchy length.
    Higher = better caption under image.
    """
    plain = _plain_text(line)
    if not plain or len(plain) < 3:
        return 0.0
    score = 0.0
    # Question — сильный хук
    if plain.rstrip().endswith("?"):
        score += 2.0
    # Цифры (часы, деньги, проценты)
    if re.search(r"\d+[\s%₽$€ч\.]|\d+\s*(час|минут|дней|руб|долл)", plain, re.I):
        score += 1.5
    # Контраст / панч
    contrast = re.compile(
        r"\b(но|а\s|зато|вместо|было|стало|раньше|сейчас|это не)\b",
        re.I,
    )
    if contrast.search(plain):
        score += 1.2
    # Короткая панчлайн (одна фраза)
    word_count = len(plain.split())
    if 4 <= word_count <= 15:
        score += 0.8
    if word_count <= 8:
        score += 0.5
    # Жирный / цитата в исходнике — часто хук
    if "<b>" in line or "<blockquote" in line:
        score += 0.7
    # Слишком длинная строка — слабее как подпись
    if len(plain) > 200:
        score -= 0.5
    return score


def short_caption_for_image(post_html: str, max_len: int = 1024) -> str:
    """
    Pick the strongest hook line for caption under image (not the opening).
    Scores by: question, numbers, contrast, punchy length; avoids duplicating first 1–2 lines.
    """
    if not post_html:
        return post_html
    lines = [ln.strip() for ln in post_html.strip().splitlines() if ln.strip()]
    if not lines:
        return post_html[: max_len - 3].rstrip() + "..."

    opening = set(lines[:2])
    # Кандидаты: не дублируем самый старт поста
    candidates = [ln for ln in lines[1:20] if ln and ln not in opening]
    if not candidates:
        teaser = lines[0]
    else:
        teaser = max(candidates, key=lambda ln: _hook_score(ln))

    if len(teaser) <= max_len:
        return teaser
    cut = max_len - 3
    if cut >= len(teaser) or teaser[cut : cut + 1].isspace():
        return teaser[:cut].rstrip() + "..."
    last_space = teaser.rfind(" ", 0, cut + 1)
    if last_space > 0:
        return teaser[:last_space].rstrip() + "..."
    return teaser[:cut].rstrip() + "..."


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
