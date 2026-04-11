from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from app.db import get_connection
from app.errors import AppError


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
RESULT_VIEWS = {"raw", "clean"}
EXPORT_FORMATS = {"json", "csv"}


@dataclass(slots=True)
class RawItem:
    news_id: str | None
    news_date: str | None
    news_title: str | None
    news_content: str | None
    source_url: str
    raw_payload: dict[str, Any]


def save_raw_items(
    task_id: str,
    items: list[RawItem],
    fetched_at: str,
    connection: Any | None = None,
) -> int:
    if not items:
        return 0

    if connection is None:
        with get_connection() as managed_connection:
            return save_raw_items(task_id, items, fetched_at, connection=managed_connection)

    for item in items:
        connection.execute(
            """
            INSERT INTO raw_items (
                task_id, news_id, news_date, news_title, news_content,
                source_url, fetched_at, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                item.news_id,
                item.news_date,
                item.news_title,
                item.news_content,
                item.source_url,
                fetched_at,
                json.dumps(item.raw_payload, ensure_ascii=True),
            ),
        )
    return len(items)


def run_cleaning(task_id: str) -> dict[str, Any]:
    _ensure_task_exists(task_id)
    cleaned_at = _now()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, news_id, news_date, news_title, news_content, source_url
            FROM raw_items
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()

        connection.execute("DELETE FROM clean_items WHERE task_id = ?", (task_id,))

        clean_done_count = 0
        clean_failed_count = 0

        for row in rows:
            try:
                clean_news_date = _normalize_date(row["news_date"])
                clean_news_title = _normalize_text(row["news_title"])
                clean_news_content = _normalize_text(row["news_content"])
                dedup_key = _build_dedup_key(row["news_id"], clean_news_title, clean_news_date)

                inserted = connection.execute(
                    """
                    INSERT OR IGNORE INTO clean_items (
                        raw_id, task_id, clean_news_date, clean_news_title,
                        clean_news_content, dedup_key, clean_status, cleaned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'clean_done', ?)
                    """,
                    (
                        row["id"],
                        task_id,
                        clean_news_date,
                        clean_news_title,
                        clean_news_content,
                        dedup_key,
                        cleaned_at,
                    ),
                )
                if inserted.rowcount == 1:
                    clean_done_count += 1
            except Exception:
                clean_failed_count += 1
                failed_key = f"failed:{row['id']}"
                connection.execute(
                    """
                    INSERT INTO clean_items (
                        raw_id, task_id, clean_news_date, clean_news_title,
                        clean_news_content, dedup_key, clean_status, cleaned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'clean_failed', ?)
                    """,
                    (
                        row["id"],
                        task_id,
                        None,
                        None,
                        None,
                        failed_key,
                        cleaned_at,
                    ),
                )

        connection.execute(
            """
            UPDATE tasks
            SET clean_done_count = ?
            WHERE task_id = ?
            """,
            (clean_done_count, task_id),
        )
        _insert_event_log(
            connection,
            task_id,
            "clean_item_success",
            {
                "clean_done_count": clean_done_count,
                "clean_failed_count": clean_failed_count,
                "raw_total": len(rows),
            },
            cleaned_at,
        )

    return {
        "task_id": task_id,
        "raw_total": len(rows),
        "clean_done_count": clean_done_count,
        "clean_failed_count": clean_failed_count,
    }


def list_results(
    task_id: str,
    view: str = "clean",
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
    query: str | None = None,
) -> dict[str, Any]:
    _ensure_task_exists(task_id)
    normalized_view = view.strip().lower()
    if normalized_view not in RESULT_VIEWS:
        raise AppError(1001, "view must be one of raw, clean")

    normalized_page = _normalize_pagination(page, "page", minimum=1, maximum=1_000_000)
    normalized_page_size = _normalize_pagination(page_size, "page_size", minimum=1, maximum=MAX_PAGE_SIZE)
    keyword = (query or "").strip()
    offset = (normalized_page - 1) * normalized_page_size

    with get_connection() as connection:
        if normalized_view == "raw":
            where_sql = "WHERE task_id = ?"
            params: list[Any] = [task_id]
            if keyword:
                where_sql += " AND (COALESCE(news_title, '') LIKE ? OR COALESCE(news_content, '') LIKE ?)"
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            total_row = connection.execute(
                f"SELECT COUNT(*) AS total FROM raw_items {where_sql}",
                params,
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT id, news_id, news_date, news_title, news_content, source_url, fetched_at
                FROM raw_items
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, normalized_page_size, offset],
            ).fetchall()
            items = [dict(row) for row in rows]
        else:
            where_sql = "WHERE task_id = ?"
            params = [task_id]
            if keyword:
                where_sql += (
                    " AND (COALESCE(clean_news_title, '') LIKE ? OR COALESCE(clean_news_content, '') LIKE ?)"
                )
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            total_row = connection.execute(
                f"SELECT COUNT(*) AS total FROM clean_items {where_sql}",
                params,
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT
                    id, raw_id, clean_news_date, clean_news_title,
                    clean_news_content, dedup_key, clean_status, cleaned_at
                FROM clean_items
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, normalized_page_size, offset],
            ).fetchall()
            items = [dict(row) for row in rows]

    return {
        "task_id": task_id,
        "view": normalized_view,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total": total_row["total"],
        "items": items,
    }


def export_results(task_id: str, export_format: str) -> dict[str, Any]:
    _ensure_task_exists(task_id)
    normalized_format = export_format.strip().lower()
    if normalized_format not in EXPORT_FORMATS:
        raise AppError(1001, "format must be one of json, csv")

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id, raw_id, clean_news_date, clean_news_title,
                clean_news_content, dedup_key, clean_status, cleaned_at
            FROM clean_items
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()

    items = [dict(row) for row in rows]
    filename = f"{task_id}_clean_results.{normalized_format}"

    if normalized_format == "json":
        content = json.dumps(items, ensure_ascii=False, indent=2)
        return {
            "filename": filename,
            "media_type": "application/json; charset=utf-8",
            "content": content.encode("utf-8"),
        }

    buffer = io.StringIO()
    fieldnames = [
        "id",
        "raw_id",
        "clean_news_date",
        "clean_news_title",
        "clean_news_content",
        "dedup_key",
        "clean_status",
        "cleaned_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(items)
    return {
        "filename": filename,
        "media_type": "text/csv; charset=utf-8",
        "content": buffer.getvalue().encode("utf-8"),
    }


def _normalize_date(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(normalized, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return normalized


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = BeautifulSoup(html.unescape(value), "html.parser").get_text(" ", strip=True)
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed or None


def _build_dedup_key(news_id: str | None, clean_news_title: str | None, clean_news_date: str | None) -> str:
    if news_id:
        return f"news_id:{news_id.strip()}"
    source = f"{clean_news_title or ''}|{clean_news_date or ''}"
    return "title_date:" + hashlib.sha1(source.encode("utf-8")).hexdigest()


def _normalize_pagination(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise AppError(1001, f"{field} must be an integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise AppError(1001, f"{field} must be an integer") from exc
    if normalized < minimum or normalized > maximum:
        raise AppError(1001, f"{field} must be between {minimum} and {maximum}")
    return normalized


def _ensure_task_exists(task_id: str) -> None:
    with get_connection() as connection:
        row = connection.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise AppError(2001)


def _insert_event_log(connection: Any, task_id: str, event_type: str, payload: dict[str, Any], created_at: str) -> None:
    connection.execute(
        """
        INSERT INTO event_logs (task_id, event_type, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, event_type, json.dumps(payload, ensure_ascii=True), created_at),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
