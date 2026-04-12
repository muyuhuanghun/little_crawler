from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlsplit

from app.config import get_settings


DB_PATH: Path | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_name TEXT,
    root_url TEXT NOT NULL,
    fetch_mode TEXT NOT NULL DEFAULT 'http',
    status TEXT NOT NULL,
    limit_count INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    total_count INTEGER NOT NULL DEFAULT 0,
    done_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    clean_done_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    url TEXT NOT NULL,
    state TEXT NOT NULL,
    hop_count INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 100,
    next_run_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(task_id, url),
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS command_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    command TEXT NOT NULL,
    result_code INTEGER NOT NULL,
    result_message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    news_id TEXT,
    news_date TEXT,
    news_title TEXT,
    news_content TEXT,
    source_url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    raw_payload_json TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clean_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    clean_news_date TEXT,
    clean_news_title TEXT,
    clean_news_content TEXT,
    dedup_key TEXT NOT NULL,
    clean_status TEXT NOT NULL,
    cleaned_at TEXT NOT NULL,
    UNIQUE(task_id, dedup_key),
    FOREIGN KEY(raw_id) REFERENCES raw_items(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
"""


def get_connection() -> sqlite3.Connection:
    db_path = _resolve_db_path()
    if db_path == Path(":memory:"):
        connection = sqlite3.connect(":memory:")
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    _ensure_tasks_fetch_mode(connection)
    _ensure_queue_items_hop_count(connection)
    _ensure_results_tables(connection)
    return connection


def init_db() -> None:
    with get_connection() as connection:
        pass


def _resolve_db_path() -> Path:
    if DB_PATH is not None:
        return DB_PATH

    settings = get_settings()
    parsed = urlsplit(settings.db_url)
    if parsed.scheme != "sqlite":
        raise ValueError(
            f"Unsupported PYMS_DB_URL scheme '{parsed.scheme}'. "
            "Current runtime only supports sqlite:///... for now."
        )

    raw_path = unquote(parsed.path or "")
    if not raw_path:
        raise ValueError("PYMS_DB_URL must include a sqlite path, for example sqlite:///data/app.db")
    if raw_path == "/:memory:":
        return Path(":memory:")

    # Normalize windows absolute path represented as /C:/...
    if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        normalized = raw_path[1:]
    elif raw_path.startswith("//"):
        normalized = raw_path
    elif raw_path.startswith("/"):
        normalized = raw_path[1:]
    else:
        normalized = raw_path
    return Path(normalized)


def _ensure_queue_items_hop_count(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(queue_items)").fetchall()
    }
    if "hop_count" not in columns:
        connection.execute(
            "ALTER TABLE queue_items ADD COLUMN hop_count INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_tasks_fetch_mode(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
    }
    if "fetch_mode" not in columns:
        connection.execute(
            "ALTER TABLE tasks ADD COLUMN fetch_mode TEXT NOT NULL DEFAULT 'http'"
        )


def _ensure_results_tables(connection: sqlite3.Connection) -> None:
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "raw_items" not in tables:
        connection.execute(
            """
            CREATE TABLE raw_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                news_id TEXT,
                news_date TEXT,
                news_title TEXT,
                news_content TEXT,
                source_url TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                raw_payload_json TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            )
            """
        )
    if "clean_items" not in tables:
        connection.execute(
            """
            CREATE TABLE clean_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                clean_news_date TEXT,
                clean_news_title TEXT,
                clean_news_content TEXT,
                dedup_key TEXT NOT NULL,
                clean_status TEXT NOT NULL,
                cleaned_at TEXT NOT NULL,
                UNIQUE(task_id, dedup_key),
                FOREIGN KEY(raw_id) REFERENCES raw_items(id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            )
            """
        )
