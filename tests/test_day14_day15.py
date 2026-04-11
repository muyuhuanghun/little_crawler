from __future__ import annotations

import os
import shutil
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.cleaning import RawItem
from app.command_engine import execute_command
from app.server import create_app
from app.service import get_task
from app.worker import CrawlResult, reset_fetcher, set_fetcher, shutdown_queue_runner


class DayFourteenDayFifteenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path("tests/.tmp") / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        db.DB_PATH = self.temp_dir / "app.db"

    def tearDown(self) -> None:
        reset_fetcher()
        shutdown_queue_runner()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_api_key_protects_v1_routes_when_configured(self) -> None:
        with patch.dict(os.environ, {"PYMS_API_KEY": "secret-key"}, clear=False):
            with TestClient(create_app()) as client:
                unauthorized = client.get("/v1/tasks")
                authorized = client.get("/v1/tasks", headers={"Authorization": "Bearer secret-key"})
                health = client.get("/v1/health")

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unauthorized.json()["code"], 1004)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["data"]["auth"]["api_key_required"])

    def test_queue_endpoint_returns_pagination_and_counts(self) -> None:
        set_fetcher(
            lambda url: CrawlResult(
                discovered_urls=[
                    "https://example.com/a",
                    "https://example.com/b",
                    "https://example.com/c",
                ],
                status_code=200,
                page_title="Root",
                raw_items=[
                    RawItem(
                        news_id="page-001",
                        news_date="2026-04-10",
                        news_title="Pagination",
                        news_content="Queue pagination body",
                        source_url=url,
                        raw_payload={"kind": "queue"},
                    )
                ],
            )
        )

        started = execute_command("crawl start url=https://example.com/news limit=4 depth=2")
        self._wait_for_task_count(started["task_id"], expected_total=4)

        with TestClient(create_app()) as client:
            response = client.get(
                f"/v1/tasks/{started['task_id']}/queue",
                params={"state": "all", "page": 1, "page_size": 2},
            )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["data"]["page"], 1)
        self.assertEqual(body["data"]["page_size"], 2)
        self.assertEqual(body["data"]["total"], 4)
        self.assertEqual(len(body["data"]["items"]), 2)
        self.assertIn("done", body["data"]["counts_by_state"])
        self.assertIn("pending", body["data"]["counts_by_state"])

    def _wait_for_task_count(self, task_id: str, expected_total: int, timeout_seconds: float = 3) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            task = get_task(task_id)
            if task["total_count"] >= expected_total:
                return
            time.sleep(0.05)
        self.fail(f"task did not reach expected total count: {task_id}")


if __name__ == "__main__":
    unittest.main()
