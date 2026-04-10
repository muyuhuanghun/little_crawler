from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.command_engine import execute_command
from app.server import create_app
from app.service import get_task, submit_task
from app.worker import reset_fetcher, shutdown_queue_runner


class DayThreeDayFourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path("tests/.tmp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        db.DB_PATH = self.temp_dir / f"{uuid.uuid4().hex}.db"
        self.client = TestClient(create_app())
        db.init_db()

    def tearDown(self) -> None:
        self.client.close()
        reset_fetcher()
        shutdown_queue_runner()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_help_command(self) -> None:
        result = execute_command("help")

        self.assertIn("supported commands", result["output"])
        self.assertIsNone(result["task_id"])

    def test_crawl_start_creates_running_task(self) -> None:
        result = execute_command("crawl start url=https://example.com/news limit=10 depth=2 task_name=daily")

        task = get_task(result["task_id"])
        self.assertEqual(task["status"], "running")
        self.assertIsNotNone(task["started_at"])
        self.assertEqual(task["task_name"], "daily")

    def test_pause_resume_stop_commands_change_status(self) -> None:
        created = execute_command("crawl start url=https://example.com/news")

        paused = execute_command(f"crawl pause task_id={created['task_id']}")
        self.assertIn("task paused", paused["output"])
        self.assertEqual(get_task(created["task_id"])["status"], "paused")

        resumed = execute_command(f"crawl resume task_id={created['task_id']}")
        self.assertIn("task resumed", resumed["output"])
        self.assertEqual(get_task(created["task_id"])["status"], "running")

        stopped = execute_command(f"crawl stop task_id={created['task_id']}")
        self.assertIn("task stopped", stopped["output"])
        task = get_task(created["task_id"])
        self.assertEqual(task["status"], "stopped")
        self.assertIsNotNone(task["ended_at"])

    def test_queue_list_command_returns_preview(self) -> None:
        created = submit_task({"url": "https://example.com/news"})

        result = execute_command(f"queue list task_id={created['task_id']} state=pending")

        self.assertIn("state=pending", result["output"])
        self.assertIn("total=1", result["output"])

    def test_command_endpoint_uses_supplied_request_id_and_logs_result(self) -> None:
        response = self.client.post(
            "/v1/command",
            json={
                "command": "crawl start url=https://example.com/news limit=5 depth=1",
                "request_id": "req_manual_001",
            },
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["request_id"], "req_manual_001")
        self.assertIn("task started", body["data"]["output"])

        with db.get_connection() as connection:
            row = connection.execute(
                "SELECT request_id, command, result_code FROM command_logs ORDER BY id DESC LIMIT 1"
            ).fetchone()

        self.assertEqual(row["request_id"], "req_manual_001")
        self.assertEqual(row["result_code"], 0)

    def test_command_endpoint_returns_app_error_payload(self) -> None:
        response = self.client.post(
            "/v1/command",
            json={"command": "crawl pause task_id=task_missing", "request_id": "req_missing"},
        )

        body = response.json()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(body["request_id"], "req_missing")
        self.assertEqual(body["code"], 2001)


if __name__ == "__main__":
    unittest.main()
