from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.db import get_connection
from app.errors import AppError


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
PBKDF2_ITERATIONS = 240_000


def register_user(username: str, password: str) -> dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_password = _normalize_password(password)
    password_hash = _hash_password(normalized_password)
    now = _now()

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if existing is not None:
            raise AppError(1001, "username already exists")
        connection.execute(
            """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (normalized_username, password_hash, now),
        )
    return {"username": normalized_username}


def login_user(username: str, password: str) -> dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_password = _normalize_password(password)
    now = _now()
    settings = get_settings()

    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if user is None or not _verify_password(normalized_password, user["password_hash"]):
            raise AppError(1004, "invalid username or password")

        token = secrets.token_urlsafe(48)
        token_hash = _hash_token(token)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)).isoformat()
        connection.execute(
            """
            INSERT INTO sessions (user_id, token_hash, created_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (user["id"], token_hash, now, expires_at),
        )

    return {
        "token": token,
        "user": {"id": user["id"], "username": user["username"]},
        "expires_at": expires_at,
    }


def get_session_user(token: str) -> dict[str, Any] | None:
    normalized = (token or "").strip()
    if not normalized:
        return None

    token_hash = _hash_token(normalized)
    now = _now()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT u.id, u.username, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "expires_at": row["expires_at"]}


def logout_session(token: str) -> None:
    normalized = (token or "").strip()
    if not normalized:
        return
    now = _now()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE sessions
            SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (now, _hash_token(normalized)),
        )


def _normalize_username(username: str) -> str:
    normalized = (username or "").strip()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise AppError(1001, "username must match [A-Za-z0-9_.-]{3,64}")
    return normalized


def _normalize_password(password: str) -> str:
    normalized = password or ""
    if len(normalized) < 8 or len(normalized) > 128:
        raise AppError(1001, "password length must be between 8 and 128")
    return normalized


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds_text, salt_hex, hash_hex = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    rounds = int(rounds_text)
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    calculated = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(expected, calculated)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
