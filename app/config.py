from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    app_env: str
    host: str
    port: int
    api_key: str | None
    db_url: str
    redis_url: str
    queue_backend: str
    queue_page_size_default: int
    queue_page_size_max: int
    result_page_size_default: int
    result_page_size_max: int

    @property
    def api_key_enabled(self) -> bool:
        return bool(self.api_key)


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("PYMS_APP_ENV", "development").strip().lower() or "development",
        host=os.getenv("PYMS_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_read_int("PYMS_PORT", 8000, minimum=1, maximum=65535),
        api_key=_read_optional("PYMS_API_KEY"),
        db_url=os.getenv("PYMS_DB_URL", "sqlite:///data/app.db").strip() or "sqlite:///data/app.db",
        redis_url=os.getenv("PYMS_REDIS_URL", "redis://127.0.0.1:6379/0").strip()
        or "redis://127.0.0.1:6379/0",
        queue_backend=_read_choice("PYMS_QUEUE_BACKEND", "inprocess", {"inprocess", "external"}),
        queue_page_size_default=_read_int("PYMS_QUEUE_PAGE_SIZE", 20, minimum=1, maximum=100),
        queue_page_size_max=_read_int("PYMS_QUEUE_PAGE_SIZE_MAX", 100, minimum=1, maximum=500),
        result_page_size_default=_read_int("PYMS_RESULT_PAGE_SIZE", 20, minimum=1, maximum=100),
        result_page_size_max=_read_int("PYMS_RESULT_PAGE_SIZE_MAX", 100, minimum=1, maximum=500),
    )


def _read_optional(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _read_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = int(raw.strip())
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _read_choice(name: str, default: str, choices: set[str]) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {allowed}")
    return value
