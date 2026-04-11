from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from app import db
from app.worker import DEFAULT_HEADERS, default_fetch_url, shutdown_queue_runner


class DayTwelveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path("tests/.tmp") / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        db.DB_PATH = self.temp_dir / "app.db"
        db.init_db()

    def tearDown(self) -> None:
        shutdown_queue_runner()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_fetch_url_decodes_meta_declared_gb18030_content(self) -> None:
        html = (
            '<html><head><meta charset="gb2312"><title>电子科大新闻</title></head>'
            '<body><p>欢迎访问新闻网</p><a href="/next">next</a></body></html>'
        )
        response = requests.Response()
        response.status_code = 200
        response._content = html.encode("gb18030")
        response.headers["Content-Type"] = "text/html"
        response.encoding = "iso-8859-1"

        mock_session = MagicMock()
        mock_session.get.return_value = response

        with patch("app.worker.assert_public_network_target", return_value="https://example.com/news"):
            with patch("app.worker.requests.Session", return_value=mock_session):
                result = default_fetch_url("https://example.com/news")

        self.assertEqual(result.page_title, "电子科大新闻")
        self.assertEqual(result.discovered_urls, ["https://example.com/next"])
        self.assertEqual(result.raw_items[0].news_content, "欢迎访问新闻网")
        self.assertEqual(result.raw_items[0].raw_payload["resolved_encoding"], "gb18030")
        self.assertEqual(result.raw_items[0].raw_payload["content_type"], "text/html")
        mock_session.get.assert_called_once_with(
            "https://example.com/news",
            headers=DEFAULT_HEADERS,
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
