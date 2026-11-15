"""Application settings loaded from environment variables / the .env file.

Unlike the class example's ``config.py``, nothing happens at import time:
settings are loaded only when ``load_settings()`` is called, and a missing key
raises ``ConfigError`` (which the UI can display) instead of ``SystemExit``
(which would kill the Streamlit server).
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .exceptions import ConfigError

DEFAULT_MODEL = "openai/gpt-oss-120b"
_PLACEHOLDER_KEYS = {"", "paste_your_key_here", "your_groq_api_key_here"}


@dataclass(frozen=True)
class Settings:
    # repr=False keeps the secret key out of logs and error messages.
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    timeout: float = 90.0      # seconds per LLM request
    max_retries: int = 2       # automatic retries by the Groq SDK (rate limits, 5xx, network)
    max_revisions: int = 2     # reviewer -> writer fix rounds
    max_steps: int = 8         # cap on planner steps (controls cost)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read an int env var, falling back to the default if missing or invalid."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}.") from None
    return max(minimum, min(maximum, value))


def load_settings() -> Settings:
    """Load settings from the environment (and the .env file, if present)."""
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key in _PLACEHOLDER_KEYS:
        raise ConfigError(
            "GROQ_API_KEY not found. Copy .env.example to .env and paste your "
            "Groq key in it (get one at https://console.groq.com/keys)."
        )

    return Settings(
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "").strip() or DEFAULT_MODEL,
        max_retries=_env_int("MAX_RETRIES", 2, 0, 5),
        max_revisions=_env_int("MAX_REVISIONS", 2, 0, 5),
        max_steps=_env_int("MAX_STEPS", 8, 2, 12),
    )
