from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.cleaning import RawItem, save_raw_items
from app.config import get_settings
from app.db import get_connection
from app.errors import AppError
from app.security import assert_public_network_target, validate_target_url
from app.state_machine import TaskStatus


POLL_INTERVAL_SECONDS = 0.05
REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
}
ENCODING_CANDIDATES = ("utf-8", "gb18030", "gbk", "gb2312", "big5")


@dataclass(slots=True)
class CrawlResult:
    discovered_urls: list[str]
    status_code: int
    page_title: str | None = None
    raw_items: list[RawItem] | None = None


FetchFunction = Callable[[str], CrawlResult]


def default_fetch_url(url: str) -> CrawlResult:
    assert_public_network_target(url)
    session = requests.Session()
    response = session.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    html_text, resolved_encoding = _decode_response(response)
    return _build_crawl_result(
        url=url,
        html_text=html_text,
        status_code=response.status_code,
        raw_payload_extra={
            "resolved_encoding": resolved_encoding,
            "content_type": response.headers.get("Content-Type"),
            "fetch_mode": "http",
        },
    )


def browser_fetch_url(url: str) -> CrawlResult:
    assert_public_network_target(url)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed; install playwright and browser binaries first") from exc

    async def _run() -> CrawlResult:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=DEFAULT_HEADERS["User-Agent"],
                    locale="zh-CN",
                )
                page = await context.new_page()
                response = await page.goto(url, wait_until="networkidle", timeout=REQUEST_TIMEOUT_SECONDS * 1000)
                html_text = await page.content()
                status_code = response.status if response is not None else 200
                return _build_crawl_result(
                    url=url,
                    html_text=html_text,
                    status_code=status_code,
                    raw_payload_extra={
                        "fetch_mode": "browser",
                        "renderer": "playwright",
                    },
                )
            finally:
                await browser.close()

    return asyncio.run(_run())


def fetch_url(url: str, fetch_mode: str = "http") -> CrawlResult:
    if fetch_mode == "browser":
        return browser_fetch_url(url)
    return default_fetch_url(url)


def _build_crawl_result(
    url: str,
    html_text: str,
    status_code: int,
    raw_payload_extra: dict[str, object] | None = None,
) -> CrawlResult:
    soup = BeautifulSoup(html_text, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        absolute_url = urljoin(url, anchor["href"].strip())
        if absolute_url.startswith(("http://", "https://")) and absolute_url not in seen:
            seen.add(absolute_url)
            links.append(absolute_url)

    title = soup.title.get_text(strip=True) if soup.title else None
    text_blocks = [paragraph.get_text(" ", strip=True) for paragraph in soup.find_all("p")]
    content = " ".join(block for block in text_blocks if block).strip() or None
    raw_item = RawItem(
        news_id=url,
        news_date=None,
        news_title=title,
        news_content=content,
        source_url=url,
        raw_payload={
            "url": url,
            "title": title,
            "status_code": status_code,
            **(raw_payload_extra or {}),
        },
    )
    return CrawlResult(
        discovered_urls=links,
        status_code=status_code,
        page_title=title,
        raw_items=[raw_item],
    )


_fetch_url: Callable[[str, str], CrawlResult] = fetch_url
_runner: QueueRunner | None = None
_runner_lock = threading.Lock()


class NoopQueueRunner:
    def notify(self) -> None:
        return

    def shutdown(self) -> None:
        return


class QueueRunner:
    def __init__(self) -> None:
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="pyms-queue-runner", daemon=True)
        self._thread.start()

    def notify(self) -> None:
        self._wake_event.set()

    def shutdown(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        self._thread.join(timeout=1)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            worked = self._process_next_queue_item()
            if worked:
                continue
            self._wake_event.wait(POLL_INTERVAL_SECONDS)
            self._wake_event.clear()

    def _process_next_queue_item(self) -> bool:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    q.id,
                    q.task_id,
                    q.url,
                    q.hop_count,
                    t.limit_count,
                    t.depth,
                    t.fetch_mode
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
            updated = connection.execute(
                """
                UPDATE queue_items
                SET state = 'running', updated_at = ?, last_error = NULL
                WHERE id = ? AND state = 'pending'
                """,
                (now, row["id"]),
            )
            if updated.rowcount == 0:
                return True

        try:
            result = _fetch_url(row["url"], row["fetch_mode"])
        except Exception as exc:
            self._mark_item_failed(row["task_id"], row["id"], row["url"], str(exc))
            return True

        self._mark_item_done(
            task_id=row["task_id"],
            queue_item_id=row["id"],
            url=row["url"],
            hop_count=row["hop_count"],
            limit_count=row["limit_count"],
            max_depth=row["depth"],
            result=result,
        )
        return True

    def _mark_item_done(
        self,
        task_id: str,
        queue_item_id: int,
        url: str,
        hop_count: int,
        limit_count: int,
        max_depth: int,
        result: CrawlResult,
    ) -> None:
        now = _now()
        with get_connection() as connection:
            task = connection.execute(
                "SELECT status FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return
            if task["status"] == TaskStatus.STOPPED.value:
                connection.execute(
                    """
                    UPDATE queue_items
                    SET state = 'canceled', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, queue_item_id),
                )
                return

            connection.execute(
                """
                UPDATE queue_items
                SET state = 'done', updated_at = ?, last_error = NULL
                WHERE id = ?
                """,
                (now, queue_item_id),
            )
            connection.execute(
                """
                UPDATE tasks
                SET done_count = done_count + 1
                WHERE task_id = ?
                """,
                (task_id,),
            )
            raw_saved_count = save_raw_items(task_id, result.raw_items or [], now, connection=connection)
            _insert_event(
                connection,
                task_id,
                "crawl_item_success",
                {
                    "url": url,
                    "status_code": result.status_code,
                    "page_title": result.page_title,
                    "raw_saved_count": raw_saved_count,
                },
                now,
            )

            if hop_count < max_depth:
                self._enqueue_discovered_urls(
                    connection=connection,
                    task_id=task_id,
                    parent_url=url,
                    hop_count=hop_count + 1,
                    limit_count=limit_count,
                    discovered_urls=result.discovered_urls,
                    created_at=now,
                )

            _finalize_task_if_needed(connection, task_id, now)

    def _mark_item_failed(self, task_id: str, queue_item_id: int, url: str, error_message: str) -> None:
        now = _now()
        with get_connection() as connection:
            task = connection.execute(
                "SELECT status FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return
            if task["status"] == TaskStatus.STOPPED.value:
                connection.execute(
                    """
                    UPDATE queue_items
                    SET state = 'canceled', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, queue_item_id),
                )
                return

            connection.execute(
                """
                UPDATE queue_items
                SET state = 'failed', updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (now, error_message, queue_item_id),
            )
            connection.execute(
                """
                UPDATE tasks
                SET failed_count = failed_count + 1
                WHERE task_id = ?
                """,
                (task_id,),
            )
            _insert_event(
                connection,
                task_id,
                "crawl_item_failed",
                {"url": url, "error": error_message},
                now,
            )
            _finalize_task_if_needed(connection, task_id, now)

    def _enqueue_discovered_urls(
        self,
        connection: object,
        task_id: str,
        parent_url: str,
        hop_count: int,
        limit_count: int,
        discovered_urls: list[str],
        created_at: str,
    ) -> None:
        count_row = connection.execute(
            "SELECT COUNT(*) AS total FROM queue_items WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        queued_total = count_row["total"]

        for discovered_url in discovered_urls:
            if queued_total >= limit_count:
                break
            try:
                validate_target_url(discovered_url)
            except AppError:
                continue

            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO queue_items (
                    task_id, url, state, hop_count, retry_count, priority, next_run_at,
                    last_error, created_at, updated_at
                ) VALUES (?, ?, 'pending', ?, 0, 100, NULL, NULL, ?, ?)
                """,
                (task_id, discovered_url, hop_count, created_at, created_at),
            )
            if inserted.rowcount == 0:
                continue

            queued_total += 1
            connection.execute(
                """
                UPDATE tasks
                SET total_count = total_count + 1
                WHERE task_id = ?
                """,
                (task_id,),
            )
            _insert_event(
                connection,
                task_id,
                "queue_enqueued",
                {"url": discovered_url, "parent_url": parent_url, "hop_count": hop_count},
                created_at,
            )


def get_queue_runner() -> QueueRunner | NoopQueueRunner:
    global _runner
    if not _is_inprocess_backend():
        return NoopQueueRunner()
    with _runner_lock:
        if _runner is None:
            _runner = QueueRunner()
        return _runner


def start_queue_runtime() -> None:
    if _is_inprocess_backend():
        get_queue_runner()


def notify_queue_runner() -> None:
    if not _is_inprocess_backend():
        return
    get_queue_runner().notify()


def set_fetcher(fetcher: FetchFunction) -> None:
    global _fetch_url
    _fetch_url = lambda url, _fetch_mode="http": fetcher(url)


def reset_fetcher() -> None:
    global _fetch_url
    _fetch_url = fetch_url


def shutdown_queue_runner() -> None:
    global _runner
    with _runner_lock:
        if _runner is None:
            return
        _runner.shutdown()
        _runner = None


def run_queue_worker_forever() -> None:
    runner = QueueRunner()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        runner.shutdown()


def _finalize_task_if_needed(connection: object, task_id: str, finished_at: str) -> None:
    task = connection.execute(
        """
        SELECT status, done_count, failed_count, total_count
        FROM tasks
        WHERE task_id = ?
        """,
        (task_id,),
    ).fetchone()
    if task is None or task["status"] != TaskStatus.RUNNING.value:
        return

    active_row = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM queue_items
        WHERE task_id = ? AND state IN ('pending', 'running')
        """,
        (task_id,),
    ).fetchone()
    if active_row["total"] > 0:
        return

    final_status = (
        TaskStatus.FAILED.value
        if task["done_count"] == 0 and task["failed_count"] > 0
        else TaskStatus.SUCCESS.value
    )
    connection.execute(
        """
        UPDATE tasks
        SET status = ?, ended_at = ?
        WHERE task_id = ?
        """,
        (final_status, finished_at, task_id),
    )
    _insert_event(
        connection,
        task_id,
        "task_finished",
        {
            "status": final_status,
            "done_count": task["done_count"],
            "failed_count": task["failed_count"],
            "total_count": task["total_count"],
        },
        finished_at,
    )


def _insert_event(
    connection: object,
    task_id: str,
    event_type: str,
    payload: dict[str, object],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO event_logs (task_id, event_type, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, event_type, json.dumps(payload, ensure_ascii=True), created_at),
    )


def _decode_response(response: requests.Response) -> tuple[str, str]:
    header_charset = _extract_charset(response.headers.get("Content-Type"))
    meta_charset = _extract_meta_charset(response.content)
    apparent_encoding = getattr(response, "apparent_encoding", None)
    declared_encoding = response.encoding

    candidates: list[str] = []
    for candidate in (
        header_charset,
        meta_charset,
        declared_encoding,
        apparent_encoding,
        *ENCODING_CANDIDATES,
    ):
        normalized = _normalize_encoding(candidate)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    for candidate in candidates:
        try:
            return response.content.decode(candidate), candidate
        except (LookupError, UnicodeDecodeError):
            continue

    fallback = response.encoding or "utf-8"
    return response.text, fallback


def _extract_charset(content_type: str | None) -> str | None:
    if not content_type:
        return None
    match = re.search(r"charset\s*=\s*['\"]?([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_meta_charset(content: bytes) -> str | None:
    head = content[:4096].decode("ascii", errors="ignore")
    direct_match = re.search(r"<meta[^>]+charset=['\"]?([A-Za-z0-9._-]+)", head, re.IGNORECASE)
    if direct_match:
        return direct_match.group(1)
    http_equiv_match = re.search(
        r"<meta[^>]+content=['\"][^'\"]*charset=([A-Za-z0-9._-]+)[^'\"]*['\"]",
        head,
        re.IGNORECASE,
    )
    if http_equiv_match:
        return http_equiv_match.group(1)
    return None


def _normalize_encoding(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    aliases = {
        "gb2312": "gb18030",
        "gbk": "gb18030",
    }
    return aliases.get(normalized, normalized)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_inprocess_backend() -> bool:
    settings = get_settings()
    return settings.queue_backend == "inprocess"
