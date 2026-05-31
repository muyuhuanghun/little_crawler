"""爬虫 Worker：抓取网页、解析内容、管理队列。"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.cleaning import RawItem, save_raw_items
from app.db import get_connection
from app.errors import AppError
from app.security import validate_target_url
from app.state_machine import TaskStatus


POLL_INTERVAL = 0.05
REQUEST_TIMEOUT = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@dataclass
class CrawlResult:
    """一次抓取的结果。"""
    discovered_urls: list[str]
    status_code: int
    page_title: str | None = None
    raw_items: list[RawItem] | None = None


FetchFunction = Callable[[str], CrawlResult]


def default_fetch_url(url: str) -> CrawlResult:
    """用 requests 抓取一个网页。"""
    validate_target_url(url)
    session = requests.Session()
    resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    html_text = resp.text
    return _parse_html(url, html_text, resp.status_code)


def _parse_html(url: str, html_text: str, status_code: int) -> CrawlResult:
    """从 HTML 中提取链接、标题、正文。"""
    soup = BeautifulSoup(html_text, "html.parser")

    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        absolute = urljoin(url, a["href"].strip())
        if absolute.startswith(("http://", "https://")) and absolute not in seen:
            seen.add(absolute)
            links.append(absolute)

    title = soup.title.get_text(strip=True) if soup.title else None
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    content = " ".join(p for p in paragraphs if p).strip() or None

    raw_item = RawItem(
        news_id=url,
        news_date=None,
        news_title=title,
        news_content=content,
        source_url=url,
        raw_payload={"url": url, "title": title, "status_code": status_code},
    )
    return CrawlResult(
        discovered_urls=links,
        status_code=status_code,
        page_title=title,
        raw_items=[raw_item],
    )


_fetch_url: FetchFunction = default_fetch_url
_runner: QueueRunner | None = None
_runner_lock = threading.Lock()


class QueueRunner:
    """后台线程，持续消费队列中的待抓取 URL。"""

    def __init__(self) -> None:
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def notify(self) -> None:
        self._wake.set()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=1)

    def _loop(self) -> None:
        while not self._stop.is_set():
            if _process_one_item():
                continue
            self._wake.wait(POLL_INTERVAL)
            self._wake.clear()


def _process_one_item() -> bool:
    """处理一个待抓取的队列项，返回 True 表示处理了。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT q.id, q.task_id, q.url, q.hop_count, q.retry_count,
                   t.limit_count, t.depth
            FROM queue_items q
            JOIN tasks t ON t.task_id = q.task_id
            WHERE t.status = ? AND q.state = 'pending'
            ORDER BY q.priority DESC, q.id ASC
            LIMIT 1
            """,
            (TaskStatus.RUNNING.value,),
        ).fetchone()
        if row is None:
            return False

        now = _now()
        updated = conn.execute(
            "UPDATE queue_items SET state = 'running', updated_at = ? WHERE id = ? AND state = 'pending'",
            (now, row["id"]),
        )
        if updated.rowcount == 0:
            conn.commit()
            return True

        try:
            result = _fetch_url(row["url"])
        except Exception as exc:
            conn.rollback()
            _mark_failed(row["task_id"], row["id"], row["url"], str(exc))
            return True

        _mark_done(
            row["task_id"], row["id"], row["url"],
            row["hop_count"], row["limit_count"], row["depth"], result,
        )
        return True
    finally:
        conn.close()


def _mark_done(
    task_id: str, item_id: int, url: str,
    hop_count: int, limit_count: int, max_depth: int,
    result: CrawlResult,
) -> None:
    now = _now()
    conn = get_connection()
    try:
        task = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if task is None:
            return
        if task["status"] == TaskStatus.STOPPED.value:
            conn.execute("UPDATE queue_items SET state = 'canceled', updated_at = ? WHERE id = ?", (now, item_id))
            conn.commit()
            return

        conn.execute("UPDATE queue_items SET state = 'done', updated_at = ? WHERE id = ?", (now, item_id))
        conn.execute("UPDATE tasks SET done_count = done_count + 1 WHERE task_id = ?", (task_id,))
        save_raw_items(task_id, result.raw_items or [], now, connection=conn)
        _insert_event(conn, task_id, "crawl_item_success", {"url": url, "status_code": result.status_code}, now)

        if hop_count < max_depth:
            _enqueue_links(conn, task_id, url, hop_count + 1, limit_count, result.discovered_urls, now)

        _finalize_if_done(conn, task_id, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _mark_failed(task_id: str, item_id: int, url: str, error: str) -> None:
    now = _now()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE queue_items SET state = 'failed', retry_count = retry_count + 1, updated_at = ?, last_error = ? WHERE id = ?",
            (now, error, item_id),
        )
        conn.execute("UPDATE tasks SET failed_count = failed_count + 1 WHERE task_id = ?", (task_id,))
        _insert_event(conn, task_id, "crawl_item_failed", {"url": url, "error": error}, now)
        _finalize_if_done(conn, task_id, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _enqueue_links(
    conn: sqlite3.Connection, task_id: str, parent_url: str,
    hop_count: int, limit_count: int, urls: list[str], now: str,
) -> None:
    count = conn.execute("SELECT COUNT(*) AS c FROM queue_items WHERE task_id = ?", (task_id,)).fetchone()["c"]
    for url in urls:
        if count >= limit_count:
            break
        try:
            validate_target_url(url)
        except AppError:
            continue
        inserted = conn.execute(
            "INSERT OR IGNORE INTO queue_items (task_id, url, state, hop_count, retry_count, priority, last_error, created_at, updated_at) VALUES (?, ?, 'pending', ?, 0, 100, NULL, ?, ?)",
            (task_id, url, hop_count, now, now),
        )
        if inserted.rowcount == 0:
            continue
        count += 1
        conn.execute("UPDATE tasks SET total_count = total_count + 1 WHERE task_id = ?", (task_id,))
        _insert_event(conn, task_id, "queue_enqueued", {"url": url, "parent_url": parent_url, "hop_count": hop_count}, now)


def _finalize_if_done(conn: sqlite3.Connection, task_id: str, now: str) -> None:
    task = conn.execute(
        "SELECT status, done_count, failed_count, total_count FROM tasks WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    if task is None or task["status"] != TaskStatus.RUNNING.value:
        return
    active = conn.execute(
        "SELECT COUNT(*) AS c FROM queue_items WHERE task_id = ? AND state IN ('pending', 'running')",
        (task_id,),
    ).fetchone()["c"]
    if active > 0:
        return
    final = TaskStatus.FAILED.value if task["done_count"] == 0 and task["failed_count"] > 0 else TaskStatus.SUCCESS.value
    conn.execute("UPDATE tasks SET status = ?, ended_at = ? WHERE task_id = ?", (final, now, task_id))
    _insert_event(conn, task_id, "task_finished", {"status": final}, now)


def _insert_event(conn: sqlite3.Connection, task_id: str, event_type: str, payload: dict, now: str) -> None:
    conn.execute(
        "INSERT INTO event_logs (task_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
        (task_id, event_type, json.dumps(payload, ensure_ascii=True), now),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_queue_runner() -> QueueRunner:
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = QueueRunner()
        return _runner


def start_queue_runtime() -> None:
    get_queue_runner()


def notify_queue_runner() -> None:
    get_queue_runner().notify()


def set_fetcher(fetcher: FetchFunction) -> None:
    global _fetch_url
    _fetch_url = fetcher


def reset_fetcher() -> None:
    global _fetch_url
    _fetch_url = default_fetch_url


def shutdown_queue_runner() -> None:
    global _runner
    with _runner_lock:
        if _runner is not None:
            _runner.shutdown()
            _runner = None
