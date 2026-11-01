import io
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

try:
    from markitdown_service.app import app
    from markitdown_service.schemas import ConversionResult

    client = TestClient(app)
except ImportError:
    client = None


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        if client is None:
            self.skipTest("FastAPI TestClient not available in current environment")

    def test_health_check(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["plugins_enabled"])

    @patch("markitdown_service.converter.DocumentConverterService.convert_file")
    def test_sync_conversion_endpoint(self, mock_convert):
        mock_convert.return_value = ConversionResult(
            markdown="# Document Title\nSample content converted",
            char_count=40,
            title="Document Title",
        )

        test_file = io.BytesIO(b"Hello world test content")
        files = {"file": ("test.txt", test_file, "text/plain")}

        response = client.post(
            "/v1/convert",
            files=files,
            headers={"X-LLM-Model": "gpt-4o-mini"},
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "success")
        self.assertEqual(json_data["filename"], "test.txt")
        self.assertIn("Document Title", json_data["result"]["markdown"])

    @patch("markitdown_service.queue.tasks.send_webhook_notification_sync")
    @patch("markitdown_service.converter.DocumentConverterService.convert_file")
    def test_async_conversion_endpoint(self, mock_convert, mock_webhook):
        mock_convert.return_value = ConversionResult(
            markdown="# Async Result\nProcessed asynchronously",
            char_count=35,
            title="Async Result",
        )
        mock_webhook.return_value = True

        test_file = io.BytesIO(b"Sample file for async queue processing")
        files = {"file": ("async_doc.txt", test_file, "text/plain")}
        data = {
            "callback_url": "https://example.com/api/webhook",
            "callback_secret": "secret123",
            "custom_metadata": '{"request_id": "REQ-7788"}',
        }

        # 1. Post to async endpoint
        response = client.post("/v1/convert/async", files=files, data=data)
        self.assertEqual(response.status_code, 202)
        resp_data = response.json()
        self.assertEqual(resp_data["status"], "queued")
        task_id = resp_data["task_id"]

        # 2. Query task status
        task_resp = client.get(f"/v1/tasks/{task_id}")
        self.assertEqual(task_resp.status_code, 200)
        task_data = task_resp.json()
        self.assertEqual(task_data["task_id"], task_id)
        self.assertEqual(task_data["filename"], "async_doc.txt")
        self.assertEqual(task_data["custom_metadata"]["request_id"], "REQ-7788")

    def test_get_nonexistent_task(self):
        response = client.get("/v1/tasks/00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

