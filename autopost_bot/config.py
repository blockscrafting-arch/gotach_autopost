"""Configuration via .env and pydantic-settings."""
from pathlib import Path

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (parent of autopost_bot package)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Max reference photos to send to image model (Multi-Input 1-3)
MAX_REFERENCE_PHOTOS = 3


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = ""
    channel_id: str = ""
    admin_user_id: str = ""

    # Gemini (2 keys for fallback)
    gemini_api_key_1: str = ""
    gemini_api_key_2: str = ""

    # OpenRouter fallback (text)
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-3-flash-preview"

    # Model text (native Gemini API)
    gemini_model: str = "gemini-3-flash-preview"

    # Image (native Gemini API)
    gemini_image_model: str = "gemini-3.1-flash-image-preview"

    # Reference photos for "with me" image generation (path to directory)
    reference_photos_dir: str = ""

    def get_gemini_keys(self) -> list[str]:
        """Return non-empty Gemini API keys in order (primary, fallback)."""
        keys = []
        for k in (self.gemini_api_key_1, self.gemini_api_key_2):
            if k and k.strip():
                keys.append(k.strip())
        return keys

    def is_admin(self, user_id: int | str) -> bool:
        if not self.admin_user_id:
            return False
        return str(user_id) == self.admin_user_id.strip()


def get_settings() -> Settings:
    return Settings()


# Max longest side for reference photos (resize to fit API limits / speed)
REFERENCE_PHOTO_MAX_SIDE = 1024
REFERENCE_PHOTO_JPEG_QUALITY = 85


def _resize_reference_photo(data: bytes, mime: str) -> tuple[bytes, str]:
    """Resize image to max side REFERENCE_PHOTO_MAX_SIDE, output as JPEG. Returns (bytes, mime)."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        if max(w, h) <= REFERENCE_PHOTO_MAX_SIDE:
            out = io.BytesIO()
            img.save(out, "JPEG", quality=REFERENCE_PHOTO_JPEG_QUALITY)
            return (out.getvalue(), "image/jpeg")
        ratio = REFERENCE_PHOTO_MAX_SIDE / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=REFERENCE_PHOTO_JPEG_QUALITY)
        return (out.getvalue(), "image/jpeg")
    except Exception as e:
        logger.warning("Resize failed for reference photo: {}", e)
        return (data, mime)


def get_reference_photo_bytes(settings: Settings | None = None) -> list[tuple[bytes, str]]:
    """
    Load up to MAX_REFERENCE_PHOTOS images from reference_photos_dir.
    Returns list of (bytes, mime_type). Large images are resized (longest side 1024px, JPEG 85%).
    """
    s = settings or get_settings()
    dir_path = (s.reference_photos_dir or "").strip()
    if not dir_path:
        return []
    root = ROOT_DIR / dir_path if not Path(dir_path).is_absolute() else Path(dir_path)
    if not root.is_dir():
        return []
    suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    paths = sorted(
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in suffixes
    )
    result: list[tuple[bytes, str]] = []
    for p in paths[:MAX_REFERENCE_PHOTOS]:
        try:
            data = p.read_bytes()
            if not data:
                continue
            mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            if p.suffix.lower() == ".webp":
                mime = "image/webp"
            data, mime = _resize_reference_photo(data, mime)
            result.append((data, mime))
        except OSError:
            continue
    return result
