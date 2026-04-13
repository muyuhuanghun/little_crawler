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
ROLE_CHOICES = {"viewer", "operator", "admin"}


def register_user(username: str, password: str) -> dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_password = _normalize_password(password)
    password_hash = _hash_password(normalized_password)
    now = _now()

    with get_connection() as connection:
        count_row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        assigned_role = "admin" if int(count_row["total"]) == 0 else "operator"
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if existing is not None:
            raise AppError(1001, "username already exists")
        connection.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (normalized_username, password_hash, assigned_role, now),
        )
    return {"username": normalized_username, "role": assigned_role}


def login_user(username: str, password: str) -> dict[str, Any]:
    normalized_username = _normalize_username(username)
    normalized_password = _normalize_password(password)
    now = _now()
    settings = get_settings()

    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = ?",
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
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
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
            SELECT u.id, u.username, u.role, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"], "expires_at": row["expires_at"]}


def list_users() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, username, role, created_at
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def set_user_role(user_id: int, role: str) -> dict[str, Any]:
    normalized_role = _normalize_role(role)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()
        if row is None:
            raise AppError(2001, "user not found")
        connection.execute(
            """
            UPDATE users
            SET role = ?
            WHERE id = ?
            """,
            (normalized_role, int(user_id)),
        )
    return {"id": row["id"], "username": row["username"], "role": normalized_role}


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


def _normalize_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in ROLE_CHOICES:
        allowed = ", ".join(sorted(ROLE_CHOICES))
        raise AppError(1001, f"role must be one of {allowed}")
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
