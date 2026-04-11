from __future__ import annotations

import shutil
import unittest
import uuid
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app import db
from app.cleaning import RawItem
from app.command_engine import execute_command
from app.server import create_app
from app.service import get_task
from app.worker import CrawlResult, reset_fetcher, set_fetcher, shutdown_queue_runner


class DayThirteenTests(unittest.TestCase):
    def setUp(self) -> None:
        from pathlib import Path

        self.temp_dir = Path("tests/.tmp") / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        db.DB_PATH = self.temp_dir / "app.db"
        self.client = TestClient(create_app())
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        reset_fetcher()
        shutdown_queue_runner()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_wordcloud_endpoint_returns_png_from_clean_items(self) -> None:
        task_id = self._create_clean_task()

        response = self.client.post(
            f"/v1/tasks/{task_id}/wordcloud",
            json={"view": "auto", "width": 800, "height": 480, "top_n": 50},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["x-wordcloud-view"], "clean")
        self.assertIn(f"{task_id}_clean_wordcloud.png", response.headers["content-disposition"])

        generated = Image.open(BytesIO(response.content))
        self.assertEqual(generated.size, (800, 480))

    def test_wordcloud_endpoint_uses_raw_items_when_clean_missing(self) -> None:
        set_fetcher(
            lambda url: CrawlResult(
                discovered_urls=[],
                status_code=200,
                page_title="Root",
                raw_items=[
                    RawItem(
                        news_id="raw-001",
                        news_date="2026-04-10",
                        news_title="原始 新闻 标题",
                        news_content="原始 内容 内容 热词",
                        source_url=url,
                        raw_payload={"kind": "raw"},
                    )
                ],
            )
        )

        started = execute_command("crawl start url=https://example.com/news")
        self._wait_for_terminal_status(started["task_id"])

        response = self.client.post(
            f"/v1/tasks/{started['task_id']}/wordcloud",
            json={"view": "auto"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-wordcloud-view"], "raw")

    def test_wordcloud_endpoint_rejects_empty_text(self) -> None:
        set_fetcher(
            lambda url: CrawlResult(
                discovered_urls=[],
                status_code=200,
                page_title="Root",
                raw_items=[
                    RawItem(
                        news_id="empty-001",
                        news_date="2026-04-10",
                        news_title="",
                        news_content="",
                        source_url=url,
                        raw_payload={"kind": "empty"},
                    )
                ],
            )
        )

        started = execute_command("crawl start url=https://example.com/news")
        self._wait_for_terminal_status(started["task_id"])

        response = self.client.post(
            f"/v1/tasks/{started['task_id']}/wordcloud",
            json={"view": "auto"},
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], 1001)
        self.assertEqual(body["message"], "no text available for wordcloud")

    def _create_clean_task(self) -> str:
        set_fetcher(
            lambda url: CrawlResult(
                discovered_urls=[],
                status_code=200,
                page_title="Root",
                raw_items=[
                    RawItem(
                        news_id="wc-001",
                        news_date="2026-04-10",
                        news_title="人工智能 教育 创新",
                        news_content="人工智能 推动 教育 创新 发展 校园 科研",
                        source_url=url,
                        raw_payload={"kind": "clean"},
                    )
                ],
            )
        )

        started = execute_command("crawl start url=https://example.com/news")
        self._wait_for_terminal_status(started["task_id"])
        execute_command(f"clean run task_id={started['task_id']}")
        return started["task_id"]

    def _wait_for_terminal_status(self, task_id: str, timeout_seconds: float = 3) -> dict[str, object]:
        import time

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            task = get_task(task_id)
            if task["status"] in {"success", "failed", "stopped"}:
                return task
            time.sleep(0.05)
        self.fail(f"task did not reach terminal status: {task_id}")


if __name__ == "__main__":
    unittest.main()
