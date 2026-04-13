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
    queue_batch_size: int
    queue_poll_interval_seconds: float
    queue_retry_max_attempts: int
    queue_retry_backoff_base_seconds: float
    queue_retry_backoff_max_seconds: float
    celery_queue_drain_rate_limit: str | None
    celery_item_rate_limit: str | None
    auth_enabled: bool
    session_ttl_hours: int
    audit_log_enabled: bool
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
        queue_backend=_read_choice("PYMS_QUEUE_BACKEND", "inprocess", {"inprocess", "external", "celery"}),
        queue_batch_size=_read_int("PYMS_QUEUE_BATCH_SIZE", 20, minimum=1, maximum=500),
        queue_poll_interval_seconds=_read_float("PYMS_QUEUE_POLL_INTERVAL_SECONDS", 2.0, minimum=0.2, maximum=30),
        queue_retry_max_attempts=_read_int("PYMS_QUEUE_RETRY_MAX_ATTEMPTS", 2, minimum=0, maximum=20),
        queue_retry_backoff_base_seconds=_read_float(
            "PYMS_QUEUE_RETRY_BACKOFF_BASE_SECONDS",
            0.5,
            minimum=0.1,
            maximum=60,
        ),
        queue_retry_backoff_max_seconds=_read_float(
            "PYMS_QUEUE_RETRY_BACKOFF_MAX_SECONDS",
            8.0,
            minimum=0.1,
            maximum=600,
        ),
        celery_queue_drain_rate_limit=_read_optional("PYMS_CELERY_QUEUE_DRAIN_RATE_LIMIT"),
        celery_item_rate_limit=_read_optional("PYMS_CELERY_ITEM_RATE_LIMIT"),
        auth_enabled=_read_bool("PYMS_AUTH_ENABLED", False),
        session_ttl_hours=_read_int("PYMS_SESSION_TTL_HOURS", 24, minimum=1, maximum=168),
        audit_log_enabled=_read_bool("PYMS_AUDIT_LOG_ENABLED", True),
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


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _read_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = float(raw.strip())
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
