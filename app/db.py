from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from app.config import get_settings


DB_PATH: Path | None = None
_SCHEMA_INIT_LOCK = threading.Lock()
_SCHEMA_INITIALIZED: set[str] = set()


SQLITE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dead_letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    queue_item_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    retry_count INTEGER NOT NULL,
    error_message TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    role TEXT,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    request_id TEXT NOT NULL,
    source_ip TEXT,
    user_agent TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);
"""


POSTGRES_SCHEMA_STATEMENTS = [
    """
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
        created_at TIMESTAMPTZ NOT NULL,
        started_at TIMESTAMPTZ,
        ended_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS queue_items (
        id BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
        url TEXT NOT NULL,
        state TEXT NOT NULL,
        hop_count INTEGER NOT NULL DEFAULT 0,
        retry_count INTEGER NOT NULL DEFAULT 0,
        priority INTEGER NOT NULL DEFAULT 100,
        next_run_at TIMESTAMPTZ,
        last_error TEXT,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE(task_id, url)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_logs (
        id BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS command_logs (
        id BIGSERIAL PRIMARY KEY,
        request_id TEXT NOT NULL,
        command TEXT NOT NULL,
        result_code INTEGER NOT NULL,
        result_message TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_items (
        id BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
        news_id TEXT,
        news_date TEXT,
        news_title TEXT,
        news_content TEXT,
        source_url TEXT NOT NULL,
        fetched_at TIMESTAMPTZ NOT NULL,
        raw_payload_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clean_items (
        id BIGSERIAL PRIMARY KEY,
        raw_id BIGINT NOT NULL REFERENCES raw_items(id) ON DELETE CASCADE,
        task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
        clean_news_date TEXT,
        clean_news_title TEXT,
        clean_news_content TEXT,
        dedup_key TEXT NOT NULL,
        clean_status TEXT NOT NULL,
        cleaned_at TIMESTAMPTZ NOT NULL,
        UNIQUE(task_id, dedup_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'operator',
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ
    )
    """,
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'operator'",
    """
    CREATE TABLE IF NOT EXISTS dead_letters (
        id BIGSERIAL PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
        queue_item_id BIGINT NOT NULL,
        url TEXT NOT NULL,
        retry_count INTEGER NOT NULL,
        error_message TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
        username TEXT,
        role TEXT,
        action TEXT NOT NULL,
        resource TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        request_id TEXT NOT NULL,
        source_ip TEXT,
        user_agent TEXT,
        payload_json TEXT,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_logs_task_id_id ON event_logs(task_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_queue_items_task_state ON queue_items(task_id, state)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_dead_letters_task_created ON dead_letters(task_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC)",
]


class DatabaseConnection:
    def __init__(self, backend: str, raw_connection: Any) -> None:
        self.backend = backend
        self._raw = raw_connection

    def __enter__(self) -> DatabaseConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc is None:
            self._raw.commit()
        else:
            self._raw.rollback()
        self._raw.close()

    def execute(self, sql: str, params: Any = ()) -> Any:
        normalized_sql = _normalize_statement(sql, self.backend)
        normalized_params = _normalize_params(params)
        return self._raw.execute(normalized_sql, normalized_params)

    def executescript(self, sql: str) -> None:
        if self.backend == "sqlite":
            self._raw.executescript(sql)
            return
        for statement in _split_statements(sql):
            self._raw.execute(_normalize_statement(statement, self.backend))


def get_connection() -> DatabaseConnection:
    backend, target, schema_key = _resolve_database_target()
    with _SCHEMA_INIT_LOCK:
        if schema_key not in _SCHEMA_INITIALIZED:
            _initialize_schema(backend, target)
            _SCHEMA_INITIALIZED.add(schema_key)
    return _open_connection(backend, target)


def init_db() -> None:
    with get_connection():
        pass


def _open_connection(backend: str, target: str) -> DatabaseConnection:
    if backend == "sqlite":
        if target == ":memory:":
            raw = sqlite3.connect(":memory:")
        else:
            db_path = Path(target)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            raw = sqlite3.connect(str(db_path))
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        return DatabaseConnection(backend="sqlite", raw_connection=raw)

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL backend requires psycopg with binary/libpq support installed"
        ) from exc
    raw_pg = psycopg.connect(target, row_factory=dict_row)
    return DatabaseConnection(backend="postgres", raw_connection=raw_pg)


def _initialize_schema(backend: str, target: str) -> None:
    connection = _open_connection(backend, target)
    with connection:
        if backend == "sqlite":
            connection.executescript(SQLITE_SCHEMA)
            _ensure_tasks_fetch_mode(connection)
            _ensure_queue_items_hop_count(connection)
            _ensure_results_tables(connection)
            _ensure_auth_tables(connection)
            _ensure_dead_letters_table(connection)
            _ensure_audit_table(connection)
            return
        for statement in POSTGRES_SCHEMA_STATEMENTS:
            connection.execute(statement)


def _resolve_database_target() -> tuple[str, str, str]:
    if DB_PATH is not None:
        db_path = DB_PATH
        if db_path == Path(":memory:"):
            return ("sqlite", ":memory:", "sqlite::memory:")
        return ("sqlite", str(db_path), f"sqlite:{db_path}")

    settings = get_settings()
    parsed = urlsplit(settings.db_url)
    scheme = parsed.scheme.lower()
    if scheme == "sqlite":
        db_path = _resolve_sqlite_path_from_url(settings.db_url)
        if db_path == Path(":memory:"):
            return ("sqlite", ":memory:", "sqlite::memory:")
        return ("sqlite", str(db_path), f"sqlite:{db_path}")
    if scheme in {"postgres", "postgresql"}:
        return ("postgres", settings.db_url, f"postgres:{settings.db_url}")
    raise ValueError(
        f"Unsupported PYMS_DB_URL scheme '{parsed.scheme}'. "
        "Use sqlite:///... or postgresql://..."
    )


def _resolve_sqlite_path_from_url(db_url: str) -> Path:
    parsed = urlsplit(db_url)
    raw_path = unquote(parsed.path or "")
    if not raw_path:
        raise ValueError("PYMS_DB_URL must include a sqlite path, for example sqlite:///data/app.db")
    if raw_path == "/:memory:":
        return Path(":memory:")
    if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        normalized = raw_path[1:]
    elif raw_path.startswith("//"):
        normalized = raw_path
    elif raw_path.startswith("/"):
        normalized = raw_path[1:]
    else:
        normalized = raw_path
    return Path(normalized)


def _normalize_statement(sql: str, backend: str) -> str:
    statement = sql.strip()
    if backend != "postgres":
        return statement
    if "INSERT OR IGNORE INTO" in statement.upper():
        statement = re.sub(r"(?i)INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", statement)
        statement = f"{statement} ON CONFLICT DO NOTHING"
    return _replace_qmark_placeholders(statement)


def _replace_qmark_placeholders(sql: str) -> str:
    # Existing codebase uses sqlite-style '?' placeholders.
    return sql.replace("?", "%s")


def _split_statements(sql_script: str) -> list[str]:
    return [segment.strip() for segment in sql_script.split(";") if segment.strip()]


def _normalize_params(params: Any) -> Any:
    if isinstance(params, list):
        return tuple(params)
    if params is None:
        return ()
    return params


def _ensure_queue_items_hop_count(connection: DatabaseConnection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(queue_items)").fetchall()
    }
    if "hop_count" not in columns:
        connection.execute(
            "ALTER TABLE queue_items ADD COLUMN hop_count INTEGER NOT NULL DEFAULT 0"
        )


def _ensure_tasks_fetch_mode(connection: DatabaseConnection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
    }
    if "fetch_mode" not in columns:
        connection.execute(
            "ALTER TABLE tasks ADD COLUMN fetch_mode TEXT NOT NULL DEFAULT 'http'"
        )


def _ensure_results_tables(connection: DatabaseConnection) -> None:
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


def _ensure_auth_tables(connection: DatabaseConnection) -> None:
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "users" not in tables:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'operator',
                created_at TEXT NOT NULL
            )
            """
        )
    else:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "role" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'operator'")
    if "sessions" not in tables:
        connection.execute(
            """
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )


def _ensure_dead_letters_table(connection: DatabaseConnection) -> None:
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "dead_letters" in tables:
        return
    connection.execute(
        """
        CREATE TABLE dead_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            queue_item_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            retry_count INTEGER NOT NULL,
            error_message TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        )
        """
    )


def _ensure_audit_table(connection: DatabaseConnection) -> None:
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "audit_logs" in tables:
        return
    connection.execute(
        """
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            role TEXT,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            request_id TEXT NOT NULL,
            source_ip TEXT,
            user_agent TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
