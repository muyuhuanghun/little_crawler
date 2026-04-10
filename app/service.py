from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.db import get_connection
from app.errors import AppError
from app.security import validate_target_url
from app.state_machine import TaskStatus, can_transition


DEFAULT_LIMIT = 50
DEFAULT_DEPTH = 1
MAX_LIMIT = 1000
MAX_DEPTH = 5
QUEUE_STATES = {"pending", "running", "done", "failed", "canceled"}
TERMINAL_EVENT_TYPES = {"task_finished", "task_stopped"}


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
                task_id, url, state, hop_count, retry_count, priority, next_run_at,
                last_error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                url,
                "pending",
                0,
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
        _insert_event_log(
            connection,
            task_id,
            "queue_enqueued",
            {"url": url, "hop_count": 0},
            created_at,
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


def transition_task(task_id: str, target_status: str) -> dict[str, Any]:
    task = _get_task_record(task_id)

    if not can_transition(task.status, target_status):
        raise AppError(2002, f"cannot transition task from {task.status} to {target_status}")

    target = TaskStatus(target_status)
    now = _now()
    started_at = task.started_at
    ended_at = task.ended_at
    event_type = "task_updated"

    if target == TaskStatus.RUNNING:
        started_at = task.started_at or now
        ended_at = None
        event_type = "task_started" if task.status == TaskStatus.PENDING.value else "task_resumed"
    elif target == TaskStatus.PAUSED:
        event_type = "task_paused"
    elif target == TaskStatus.STOPPED:
        ended_at = now
        event_type = "task_stopped"

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE tasks
            SET status = ?, started_at = ?, ended_at = ?
            WHERE task_id = ?
            """,
            (target.value, started_at, ended_at, task_id),
        )
        if target == TaskStatus.STOPPED:
            connection.execute(
                """
                UPDATE queue_items
                SET state = 'canceled', updated_at = ?
                WHERE task_id = ? AND state IN ('pending', 'running')
                """,
                (now, task_id),
            )
        _insert_event_log(
            connection,
            task_id,
            event_type,
            {"from": task.status, "to": target.value},
            now,
        )

    if target == TaskStatus.RUNNING:
        from app.worker import notify_queue_runner

        notify_queue_runner()

    return get_task(task_id)


def list_queue_items(task_id: str, state: str | None = None) -> dict[str, Any]:
    _ensure_task_exists(task_id)
    normalized_state = None
    if state is not None:
        normalized_state = state.strip().lower()
        if normalized_state == "all":
            normalized_state = None
        elif normalized_state not in QUEUE_STATES:
            raise AppError(1001, "state must be one of pending, running, done, failed, canceled, all")

    with get_connection() as connection:
        if normalized_state is None:
            rows = connection.execute(
                """
                SELECT id, url, state, hop_count, retry_count, next_run_at, last_error, updated_at
                FROM queue_items
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (task_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, url, state, hop_count, retry_count, next_run_at, last_error, updated_at
                FROM queue_items
                WHERE task_id = ? AND state = ?
                ORDER BY id ASC
                """,
                (task_id, normalized_state),
            ).fetchall()

    items = [
        {
            "id": row["id"],
            "url": row["url"],
            "state": row["state"],
            "hop_count": row["hop_count"],
            "retry_count": row["retry_count"],
            "next_run_at": row["next_run_at"],
            "last_error": row["last_error"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]
    return {
        "task_id": task_id,
        "state": normalized_state or "all",
        "total": len(items),
        "items": items,
    }


def log_command(request_id: str, command: str, result_code: int, result_message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO command_logs (request_id, command, result_code, result_message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, command, result_code, result_message, _now()),
        )


def list_event_logs(task_id: str, after_id: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    _ensure_task_exists(task_id)
    normalized_after_id = _normalize_int(after_id, "after_id", 0, 1_000_000_000)
    normalized_limit = _normalize_int(limit, "limit", 1, 1000)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, event_type, payload_json, created_at
            FROM event_logs
            WHERE task_id = ? AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (task_id, normalized_after_id, normalized_limit),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "task_id": task_id,
            "event_type": row["event_type"],
            "timestamp": row["created_at"],
            "payload": json.loads(row["payload_json"]),
        }
        for row in rows
    ]


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


def _get_task_record(task_id: str) -> TaskRecord:
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
    return _row_to_task(row)


def _ensure_task_exists(task_id: str) -> None:
    _get_task_record(task_id)


def _insert_event_log(connection: Any, task_id: str, event_type: str, payload: dict[str, Any], created_at: str) -> None:
    connection.execute(
        """
        INSERT INTO event_logs (task_id, event_type, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, event_type, json.dumps(payload, ensure_ascii=True), created_at),
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
