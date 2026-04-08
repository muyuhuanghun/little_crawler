from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.db import get_connection
from app.errors import AppError
from app.security import validate_target_url
from app.state_machine import TaskStatus


DEFAULT_LIMIT = 50
DEFAULT_DEPTH = 1
MAX_LIMIT = 1000
MAX_DEPTH = 5


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    task_name: str | None
    root_url: str
    status: str
    limit: int
    depth: int
    total_count: int
    done_count: int
    failed_count: int
    clean_done_count: int
    created_at: str
    started_at: str | None
    ended_at: str | None

    @property
    def progress(self) -> float:
        if self.total_count <= 0:
            return 0.0
        return round(((self.done_count + self.failed_count) / self.total_count) * 100, 2)


def submit_task(payload: dict[str, Any]) -> dict[str, Any]:
    url = validate_target_url(_require_string(payload, "url"))
    limit = _normalize_int(payload.get("limit", DEFAULT_LIMIT), "limit", 1, MAX_LIMIT)
    depth = _normalize_int(payload.get("depth", DEFAULT_DEPTH), "depth", 1, MAX_DEPTH)
    task_name = payload.get("task_name")
    if task_name is not None and not isinstance(task_name, str):
        raise AppError(1001, "task_name must be a string")

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    created_at = _now()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                task_id, task_name, root_url, status, limit_count, depth,
                total_count, done_count, failed_count, clean_done_count,
                created_at, started_at, ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                task_name or task_id,
                url,
                TaskStatus.PENDING.value,
                limit,
                depth,
                1,
                0,
                0,
                0,
                created_at,
                None,
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO queue_items (
                task_id, url, state, retry_count, priority, next_run_at,
                last_error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                url,
                "pending",
                0,
                100,
                None,
                None,
                created_at,
                created_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO event_logs (task_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                task_id,
                "task_created",
                json.dumps({"root_url": url, "queued_count": 1}, ensure_ascii=True),
                created_at,
            ),
        )

    return {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "queued_count": 1,
    }


def list_tasks() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                task_id, task_name, root_url, status, limit_count, depth,
                total_count, done_count, failed_count, clean_done_count,
                created_at, started_at, ended_at
            FROM tasks
            ORDER BY created_at DESC, rowid DESC
            """
        ).fetchall()
    return [_serialize_task(_row_to_task(row)) for row in rows]


def get_task(task_id: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                task_id, task_name, root_url, status, limit_count, depth,
                total_count, done_count, failed_count, clean_done_count,
                created_at, started_at, ended_at
            FROM tasks
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    if row is None:
        raise AppError(2001)
    return _serialize_task(_row_to_task(row))


def _serialize_task(task: TaskRecord) -> dict[str, Any]:
    data = asdict(task)
    data["limit"] = data.pop("limit")
    data["progress"] = task.progress
    return data


def _row_to_task(row: Any) -> TaskRecord:
    return TaskRecord(
        task_id=row["task_id"],
        task_name=row["task_name"],
        root_url=row["root_url"],
        status=row["status"],
        limit=row["limit_count"],
        depth=row["depth"],
        total_count=row["total_count"],
        done_count=row["done_count"],
        failed_count=row["failed_count"],
        clean_done_count=row["clean_done_count"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AppError(1001, f"{field} is required")
    return value.strip()


def _normalize_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise AppError(1001, f"{field} must be an integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AppError(1001, f"{field} must be an integer") from exc
    if normalized < minimum or normalized > maximum:
        raise AppError(1001, f"{field} must be between {minimum} and {maximum}")
    return normalized


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
