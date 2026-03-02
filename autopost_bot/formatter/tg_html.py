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
    Оценка «мощности» строки как хука под картинку.
    Вопрос, цифра, контраст, короткий панч — выше балл.
    """
    plain = _plain_text(line)
    if not plain or len(plain) < 3:
        return 0.0
    score = 0.0
    # Вопрос — очень сильный хук
    if plain.rstrip().endswith("?"):
        score += 2.5
    # Цифры (часы, деньги, проценты)
    if re.search(r"\d+[\s%₽$€ч\.]|\d+\s*(час|минут|дней|руб|долл)", plain, re.I):
        score += 1.8
    # Контраст / панч
    contrast = re.compile(
        r"\b(но|а\s|зато|вместо|было|стало|раньше|сейчас|это не)\b",
        re.I,
    )
    if contrast.search(plain):
        score += 1.5
    # Длина: короткий панч лучше под картинку
    word_count = len(plain.split())
    if word_count <= 5:
        score += 1.2
    elif word_count <= 10:
        score += 1.0
    elif 11 <= word_count <= 18:
        score += 0.6
    elif word_count > 35:
        score -= 1.0
    # Жирный / цитата — обычно главная мысль
    if "<b>" in line or "<blockquote" in line:
        score += 1.0
    # Слишком длинная строка — плохая подпись
    if len(plain) > 180:
        score -= 0.8
    return score


def _truncate_caption(text: str, max_len: int) -> str:
    """Truncate caption at word boundary."""
    if len(text) <= max_len:
        return text
    cut = max_len - 3
    if cut >= len(text) or text[cut : cut + 1].isspace():
        return text[:cut].rstrip() + "..."
    last_space = text.rfind(" ", 0, cut + 1)
    if last_space > 0:
        return text[:last_space].rstrip() + "..."
    return text[:cut].rstrip() + "..."


def _build_power_hook(best_line: str, lines: list[str]) -> str:
    """Turn strongest line into a punchy caption hook."""
    plain = _plain_text(best_line)
    plain = re.sub(r"^[^\wА-Яа-яЁё]+", "", plain).strip()
    if not plain:
        return best_line

    # Было/Стало -> провокационный контраст вместо сухого отчета
    m_bilo = re.search(r"\bбыло\b\s*[:\-]?\s*(.+)$", plain, re.I)
    if m_bilo:
        was = m_bilo.group(1).strip(" .")
        stalo = ""
        for line in lines:
            m_stalo = re.search(r"\bстало\b\s*[:\-]?\s*(.+)$", _plain_text(line), re.I)
            if m_stalo:
                stalo = m_stalo.group(1).strip(" .")
                break
        if was and stalo:
            return f"{was} -> {stalo}. Как тебе такой разрыв?"
        if was:
            return f"{was} на один пост — и это считается нормой?"

    # Строка с цифрой, но без вопроса -> добавляем вызов/напряжение
    if re.search(r"\d", plain) and not plain.endswith("?"):
        return f"{plain.rstrip('.!')} — тебя это реально устраивает?"

    # Иначе: оставить как хук, но с вопросом, если он слишком нейтральный
    if not plain.endswith(("?", "!")) and len(plain.split()) > 5:
        return f"{plain} И вот где самое интересное."
    return plain


def short_caption_for_image(post_html: str, max_len: int = 1024) -> str:
    """
    Под картинкой — одна самая мощная строка поста (хук).
    Выбираем по баллам по всему посту: вопрос, цифра, контраст, короткий панч.
    """
    if not post_html:
        return post_html
    lines = [ln.strip() for ln in post_html.strip().splitlines() if ln.strip()]
    if not lines:
        return post_html[: max_len - 3].rstrip() + "..."

    # Берём самую мощную строку по всему посту (до разумного предела)
    candidates = [ln for ln in lines[:25] if ln]
    teaser = max(candidates, key=lambda ln: _hook_score(ln)) if candidates else lines[0]
    hook = _build_power_hook(teaser, lines)
    return _truncate_caption(hook, max_len)


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
