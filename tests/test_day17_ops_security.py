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
from app.command_engine import execute_command
from app.server import create_app
from app.service import get_task
from app.worker import CrawlResult, reset_fetcher, set_fetcher, shutdown_queue_runner


class DaySeventeenOpsSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path("tests/.tmp") / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        db.DB_PATH = self.temp_dir / "app.db"

    def tearDown(self) -> None:
        reset_fetcher()
        shutdown_queue_runner()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_retry_then_dead_letter(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PYMS_QUEUE_BACKEND": "inprocess",
                "PYMS_QUEUE_RETRY_MAX_ATTEMPTS": "1",
                "PYMS_QUEUE_RETRY_BACKOFF_BASE_SECONDS": "0.1",
                "PYMS_QUEUE_RETRY_BACKOFF_MAX_SECONDS": "0.2",
            },
            clear=False,
        ):
            db.init_db()
            set_fetcher(lambda _: (_ for _ in ()).throw(RuntimeError("network boom")))

            started = execute_command("crawl start url=https://example.com/news")
            task = self._wait_for_terminal_status(started["task_id"], timeout_seconds=5)

            self.assertEqual(task["status"], "failed")
            self.assertEqual(task["failed_count"], 1)

            with db.get_connection() as connection:
                queue_item = connection.execute(
                    "SELECT state, retry_count, last_error FROM queue_items WHERE task_id = ?",
                    (started["task_id"],),
                ).fetchone()
                dead_letter = connection.execute(
                    "SELECT queue_item_id, retry_count, error_message FROM dead_letters WHERE task_id = ?",
                    (started["task_id"],),
                ).fetchone()

            self.assertEqual(queue_item["state"], "failed")
            self.assertEqual(queue_item["retry_count"], 2)
            self.assertIn("network boom", queue_item["last_error"])
            self.assertIsNotNone(dead_letter)
            self.assertEqual(dead_letter["retry_count"], 2)
            self.assertIn("network boom", dead_letter["error_message"])

    def test_rbac_and_audit_log(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PYMS_AUTH_ENABLED": "true",
                "PYMS_AUDIT_LOG_ENABLED": "true",
            },
            clear=False,
        ):
            client = TestClient(create_app())
            self.addCleanup(client.close)
            db.init_db()

            admin_register = client.post(
                "/v1/auth/register",
                json={"username": "admin_user", "password": "Password123"},
            )
            self.assertEqual(admin_register.status_code, 200)
            self.assertEqual(admin_register.json()["data"]["role"], "admin")

            admin_login = client.post(
                "/v1/auth/login",
                json={"username": "admin_user", "password": "Password123"},
            )
            self.assertEqual(admin_login.status_code, 200)
            admin_token = admin_login.cookies["pyms_session"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            op_register = client.post(
                "/v1/auth/register",
                json={"username": "viewer_user", "password": "Password123"},
            )
            self.assertEqual(op_register.status_code, 200)
            self.assertEqual(op_register.json()["data"]["role"], "operator")
            target_user_id = op_register.json()["data"].get("id")
            if target_user_id is None:
                users_resp = client.get("/v1/auth/users", headers=admin_headers)
                self.assertEqual(users_resp.status_code, 200)
                target_user_id = next(
                    item["id"]
                    for item in users_resp.json()["data"]["items"]
                    if item["username"] == "viewer_user"
                )

            role_change = client.post(
                f"/v1/auth/users/{target_user_id}/role",
                headers=admin_headers,
                json={"role": "viewer"},
            )
            self.assertEqual(role_change.status_code, 200)

            viewer_login = client.post(
                "/v1/auth/login",
                json={"username": "viewer_user", "password": "Password123"},
            )
            viewer_token = viewer_login.cookies["pyms_session"]
            viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

            denied = client.post(
                "/v1/crawl/submit",
                headers=viewer_headers,
                json={"url": "https://example.com/news", "limit": 2, "depth": 1, "renderer": "http"},
            )
            self.assertEqual(denied.status_code, 403)

            allowed = client.get("/v1/tasks", headers=viewer_headers)
            self.assertEqual(allowed.status_code, 200)

            audit = client.get("/v1/audit/logs", headers=admin_headers)
            self.assertEqual(audit.status_code, 200)
            self.assertGreaterEqual(audit.json()["data"]["total"], 1)

    def _wait_for_terminal_status(self, task_id: str, timeout_seconds: float = 3) -> dict[str, object]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            task = get_task(task_id)
            if task["status"] in {"success", "failed", "stopped"}:
                return task
            time.sleep(0.05)
        self.fail(f"task did not reach terminal status: {task_id}")


if __name__ == "__main__":
    unittest.main()
