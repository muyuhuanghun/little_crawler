from __future__ import annotations

import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.server import create_app
from app.worker import shutdown_queue_runner


class DaySixteenAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path("tests/.tmp") / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        db.DB_PATH = self.temp_dir / "app.db"

    def tearDown(self) -> None:
        shutdown_queue_runner()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_auth_session_flow_with_cookie(self) -> None:
        with patch.dict(os.environ, {"PYMS_AUTH_ENABLED": "true"}, clear=False):
            with TestClient(create_app()) as client:
                tasks_unauthorized = client.get("/v1/tasks")
                self.assertEqual(tasks_unauthorized.status_code, 401)

                register = client.post(
                    "/v1/auth/register",
                    json={"username": "alice_dev", "password": "Password123!"},
                )
                self.assertEqual(register.status_code, 200)

                login = client.post(
                    "/v1/auth/login",
                    json={"username": "alice_dev", "password": "Password123!"},
                )
                self.assertEqual(login.status_code, 200)
                self.assertIn("pyms_session", login.cookies)

                token = login.cookies["pyms_session"]
                tasks_authorized = client.get(
                    "/v1/tasks",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(tasks_authorized.status_code, 200)

    def test_auth_me_requires_valid_session(self) -> None:
        with patch.dict(os.environ, {"PYMS_AUTH_ENABLED": "true"}, clear=False):
            with TestClient(create_app()) as client:
                unauthorized = client.get("/v1/auth/me")
                self.assertEqual(unauthorized.status_code, 401)

                client.post(
                    "/v1/auth/register",
                    json={"username": "bob_dev", "password": "Password123!"},
                )
                login = client.post(
                    "/v1/auth/login",
                    json={"username": "bob_dev", "password": "Password123!"},
                )
                token = login.cookies["pyms_session"]
                me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json()["data"]["user"]["username"], "bob_dev")


if __name__ == "__main__":
    unittest.main()
