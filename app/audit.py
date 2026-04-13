from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db import get_connection


def write_audit_log(
    *,
    user: dict[str, Any] | None,
    action: str,
    resource: str,
    status_code: int,
    request_id: str,
    source_ip: str | None,
    user_agent: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_logs (
                user_id, username, role, action, resource, status_code, request_id,
                source_ip, user_agent, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.get("id") if user else None,
                user.get("username") if user else None,
                user.get("role") if user else None,
                action,
                resource,
                int(status_code),
                request_id,
                source_ip,
                user_agent,
                json.dumps(payload or {}, ensure_ascii=True),
                _now(),
            ),
        )


def list_audit_logs(page: int = 1, page_size: int = 50) -> dict[str, Any]:
    normalized_page = max(1, int(page))
    normalized_page_size = max(1, min(200, int(page_size)))
    offset = (normalized_page - 1) * normalized_page_size

    with get_connection() as connection:
        total_row = connection.execute("SELECT COUNT(*) AS total FROM audit_logs").fetchone()
        rows = connection.execute(
            """
            SELECT
                id, user_id, username, role, action, resource, status_code,
                request_id, source_ip, user_agent, payload_json, created_at
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (normalized_page_size, offset),
        ).fetchall()

    return {
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total": int(total_row["total"]),
        "items": [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "username": row["username"],
                "role": row["role"],
                "action": row["action"],
                "resource": row["resource"],
                "status_code": row["status_code"],
                "request_id": row["request_id"],
                "source_ip": row["source_ip"],
                "user_agent": row["user_agent"],
                "payload": json.loads(row["payload_json"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
