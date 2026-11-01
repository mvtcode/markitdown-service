"""
Full-feature End-to-End & Integration Test Suite for MarkItDown Service:
1. Plain text & structured formats: TXT, CSV, HTML, DOCX, XLSX
2. Media files: WAV audio
3. OCR across multiple extensions: PNG, JPG, PDF (with embedded scans)
4. Asynchronous Queue + Webhook Callback Notification + HMAC SHA-256 verification
5. Task polling fallback: GET /v1/tasks/{task_id}
6. API Authentication Token verification & dynamic Swagger Authorize visibility
"""

import http.server
import json
import os
from pathlib import Path
import threading
import time
import unittest

from fastapi.testclient import TestClient
from markitdown_service.app import app
from markitdown_service.config import settings
from markitdown_service.queue.webhook import generate_hmac_signature

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockWebhookHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP Server that captures callback notifications from the worker."""

    received_requests = []

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        record = {
            "path": self.path,
            "headers": dict(self.headers),
            "raw_body": body,
            "json": None,
        }
        try:
            record["json"] = json.loads(body.decode("utf-8"))
        except Exception:
            pass

        MockWebhookHandler.received_requests.append(record)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"acknowledged"}')

    def log_message(self, format, *args):
        # Silence default stderr logging during tests
        pass


class TestMarkItDownFullFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Ensure test fixtures are generated
        from tests.generate_test_fixtures import generate_all

        generate_all()

        # 2. Start mock webhook server on an ephemeral port
        MockWebhookHandler.received_requests.clear()
        cls.httpd = http.server.HTTPServer(("127.0.0.1", 0), MockWebhookHandler)
        cls.port = cls.httpd.server_port
        cls.webhook_url = f"http://127.0.0.1:{cls.port}/api/webhook"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        except Exception:
            pass

    def get_auth_headers(self, extra: dict | None = None) -> dict:
        """Helper to attach active API_AUTH_TOKEN header for protected endpoints."""
        h = {}
        if settings.API_AUTH_TOKEN:
            h["X-API-Token"] = settings.API_AUTH_TOKEN
        if extra:
            h.update(extra)
        return h

    # ==========================================
    # 1. TEST TEXT & STRUCTURED FORMATS
    # ==========================================

    def test_01_convert_plain_text(self):
        """Kiểm tra upload & convert file TXT thuần túy"""
        txt_file = FIXTURES_DIR / "sample.txt"
        with open(txt_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("sample.txt", f, "text/plain")},
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Báo Cáo Kỹ Thuật", data["result"]["markdown"])
        # Non-OCR files must not have ocr field
        self.assertIsNone(data["result"].get("ocr"))

    def test_02_convert_csv(self):
        """Kiểm tra upload & convert file CSV thành bảng Markdown"""
        csv_file = FIXTURES_DIR / "sample.csv"
        with open(csv_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("sample.csv", f, "text/csv")},
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]
        self.assertIn("Laptop Dell XPS", markdown)
        self.assertIn("Bàn phím cơ", markdown)

    def test_03_convert_html(self):
        """Kiểm tra upload & convert file HTML sang Markdown định dạng chuẩn"""
        html_file = FIXTURES_DIR / "sample.html"
        with open(html_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("sample.html", f, "text/html")},
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]
        self.assertIn("Tiêu đề bài viết HTML", markdown)
        self.assertIn("Tính năng 1", markdown)

    def test_04_convert_docx(self):
        """Kiểm tra upload & convert Word (.docx) chứa tiêu đề và bảng"""
        docx_file = FIXTURES_DIR / "sample.docx"
        if not docx_file.exists():
            self.skipTest("sample.docx not found")

        with open(docx_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={
                    "file": (
                        "sample.docx",
                        f,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]
        self.assertIn("Hợp Đồng Dịch Vụ Phần Mềm", markdown)
        self.assertIn("API Service", markdown)

    def test_05_convert_xlsx(self):
        """Kiểm tra upload & convert Excel (.xlsx) sang bảng biểu Markdown"""
        xlsx_file = FIXTURES_DIR / "sample.xlsx"
        if not xlsx_file.exists():
            self.skipTest("sample.xlsx not found")

        with open(xlsx_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={
                    "file": (
                        "sample.xlsx",
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]
        self.assertIn("DoanhThu", markdown)
        self.assertIn("100000", markdown)

    # ==========================================
    # 2. TEST MEDIA FILES
    # ==========================================

    def test_06_convert_media_audio_wav(self):
        """Kiểm tra upload & convert file Media (WAV audio)"""
        wav_file = FIXTURES_DIR / "sample_audio.wav"
        with open(wav_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("sample_audio.wav", f, "audio/wav")},
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(data["result"]["markdown"])

    def test_06b_convert_media_audio_mp3(self):
        """Kiểm tra upload & convert file Media (.mp3)"""
        mp3_file = FIXTURES_DIR / "audio-test.mp3"
        if not mp3_file.exists():
            mp3_file = Path("packages/markitdown/tests/test_files/test.mp3")
        if not mp3_file.exists():
            self.skipTest("No mp3 fixture found")

        with open(mp3_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": (mp3_file.name, f, "audio/mpeg")},
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        markdown = data["result"]["markdown"]
        self.assertIn("Audio Transcript", markdown)

    # ==========================================
    # 3. TEST OCR ACROSS DIFFERENT EXTENSIONS
    # ==========================================

    def test_07_ocr_image_png(self):
        """Kiểm tra OCR hình ảnh định dạng PNG qua LLM Vision"""
        png_file = FIXTURES_DIR / "receipt_ocr.png"

        extra_headers = {}
        if settings.DEFAULT_LLM_API_KEY:
            extra_headers["X-LLM-Api-Key"] = settings.DEFAULT_LLM_API_KEY
            extra_headers["X-LLM-Model"] = settings.DEFAULT_LLM_MODEL or "gpt-4o"

        headers = self.get_auth_headers(extra_headers)

        with open(png_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("receipt_ocr.png", f, "image/png")},
                headers=headers,
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]

        # Nếu có API Key OpenAI thực, kiểm tra chữ OCR trích xuất được
        if settings.DEFAULT_LLM_API_KEY:
            self.assertTrue(
                any(keyword in markdown.upper() for keyword in ["HOA DON", "HD-2026", "THANH TOAN", "5.000.000"]),
                f"OCR result did not contain expected text. Got: {markdown}",
            )
            # Verify OCR usage metrics are populated
            ocr_data = data["result"].get("ocr")
            self.assertIsNotNone(ocr_data, "Field 'ocr' must be present when OCR is performed")
            self.assertGreater(ocr_data["prompt_tokens"], 0)
            self.assertGreater(ocr_data["completion_tokens"], 0)
            self.assertGreater(ocr_data["total_tokens"], 0)
            self.assertIsNotNone(ocr_data["model"])
            self.assertGreaterEqual(ocr_data["call_count"], 1)
        else:
            self.assertIsNotNone(markdown)

    def test_08_ocr_image_jpg(self):
        """Kiểm tra OCR hình ảnh định dạng JPG qua LLM Vision"""
        jpg_file = FIXTURES_DIR / "receipt_ocr.jpg"

        extra_headers = {}
        if settings.DEFAULT_LLM_API_KEY:
            extra_headers["X-LLM-Api-Key"] = settings.DEFAULT_LLM_API_KEY
            extra_headers["X-LLM-Model"] = settings.DEFAULT_LLM_MODEL or "gpt-4o"

        headers = self.get_auth_headers(extra_headers)

        with open(jpg_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("receipt_ocr.jpg", f, "image/jpeg")},
                headers=headers,
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]
        if settings.DEFAULT_LLM_API_KEY:
            self.assertTrue(
                any(keyword in markdown.upper() for keyword in ["HOA DON", "HD-2026", "THANH TOAN"]),
                f"OCR result did not contain expected text. Got: {markdown}",
            )

    def test_09_ocr_pdf_with_images(self):
        """Kiểm tra xử lý PDF chứa ảnh scan kết hợp text layer"""
        pdf_file = FIXTURES_DIR / "scanned_doc.pdf"
        if not pdf_file.exists():
            self.skipTest("scanned_doc.pdf not found")

        extra_headers = {}
        if settings.DEFAULT_LLM_API_KEY:
            extra_headers["X-LLM-Api-Key"] = settings.DEFAULT_LLM_API_KEY
            extra_headers["X-LLM-Model"] = settings.DEFAULT_LLM_MODEL or "gpt-4o"

        headers = self.get_auth_headers(extra_headers)

        with open(pdf_file, "rb") as f:
            resp = client.post(
                "/v1/convert",
                files={"file": ("scanned_doc.pdf", f, "application/pdf")},
                headers=headers,
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        markdown = data["result"]["markdown"]
        # Phải chứa text layer trong PDF
        self.assertIn("Bao Cao Tai Lieu Dinh Kem", markdown)

    # ==========================================
    # 4. TEST ASYNC QUEUE + WEBHOOK CALLBACK
    # ==========================================

    def test_10_async_queue_and_webhook_callback(self):
        """
        Kiểm tra luồng Queue & Webhook Callback thực tế:
        1. Gửi file vào POST /v1/convert/async kèm callback_url & secret
        2. Nhận 202 Accepted và task_id
        3. Chờ Background Worker xử lý xong
        4. Xác thực Webhook nhận được HTTP POST:
           - Trạng thái: completed
           - Chữ ký bảo mật: X-MarkItDown-Signature đúng HMAC-SHA256
           - Custom metadata được trả về nguyên vẹn
        5. Kiểm tra GET /v1/tasks/{task_id}
        """
        secret_key = "super_secret_webhook_token_2026"
        custom_meta = {"invoice_id": "INV-8899", "department": "Accounting"}

        MockWebhookHandler.received_requests.clear()

        txt_file = FIXTURES_DIR / "sample.txt"
        with open(txt_file, "rb") as f:
            files = {"file": ("async_test.txt", f, "text/plain")}
            form_data = {
                "callback_url": self.webhook_url,
                "callback_secret": secret_key,
                "custom_metadata": json.dumps(custom_meta),
            }

            resp = client.post(
                "/v1/convert/async",
                files=files,
                data=form_data,
                headers=self.get_auth_headers(),
            )

        self.assertEqual(resp.status_code, 202, resp.text)
        async_data = resp.json()
        self.assertEqual(async_data["status"], "queued")
        task_id = async_data["task_id"]

        # Wait for the background task to complete and invoke the webhook
        timeout_seconds = 10.0
        start = time.time()
        while time.time() - start < timeout_seconds:
            if len(MockWebhookHandler.received_requests) > 0:
                break
            time.sleep(0.2)

        self.assertGreater(
            len(MockWebhookHandler.received_requests),
            0,
            f"Webhook callback was not received within {timeout_seconds} seconds!",
        )

        # Inspect the captured webhook request
        captured = MockWebhookHandler.received_requests[0]
        self.assertEqual(captured["path"], "/api/webhook")

        # Verify HMAC-SHA256 signature
        raw_body = captured["raw_body"]
        expected_sig = generate_hmac_signature(raw_body, secret_key)
        actual_sig = captured["headers"].get("X-MarkItDown-Signature") or captured["headers"].get(
            "x-markitdown-signature"
        )
        self.assertEqual(actual_sig, expected_sig, "HMAC-SHA256 signature does not match!")

        # Verify Event and Task ID Headers
        event_header = captured["headers"].get("X-MarkItDown-Event") or captured["headers"].get("x-markitdown-event")
        self.assertEqual(event_header, "task.completed")

        # Verify Payload JSON contents
        payload = captured["json"]
        self.assertIsNotNone(payload)
        self.assertEqual(payload["event"], "task.completed")
        self.assertEqual(payload["task_id"], task_id)
        self.assertEqual(payload["status"], "completed")
        self.assertIn("Báo Cáo Kỹ Thuật", payload["result"]["markdown"])
        self.assertEqual(payload["custom_metadata"], custom_meta)

        # Verify Polling Endpoint GET /v1/tasks/{task_id}
        poll_resp = client.get(f"/v1/tasks/{task_id}", headers=self.get_auth_headers())
        self.assertEqual(poll_resp.status_code, 200)
        task_state = poll_resp.json()
        self.assertEqual(task_state["status"], "completed")
        self.assertIn("Báo Cáo Kỹ Thuật", task_state["result"]["markdown"])

    # ==========================================
    # 5. TEST API TOKEN AUTHENTICATION & SWAGGER VISIBILITY
    # ==========================================

    def test_11_api_token_authentication(self):
        """Kiểm tra cơ chế chặn truy cập và tự động ẩn/hiện nút Authorize trên Swagger"""
        original_token = settings.API_AUTH_TOKEN
        try:
            settings.API_AUTH_TOKEN = "test_secure_token_999"

            txt_file = FIXTURES_DIR / "sample.txt"
            with open(txt_file, "rb") as f:
                # 1. Không truyền token -> 401 Unauthorized
                resp_no_token = client.post("/v1/convert", files={"file": ("sample.txt", f, "text/plain")})
                self.assertEqual(resp_no_token.status_code, 401)

            with open(txt_file, "rb") as f:
                # 2. Truyền token sai -> 401 Unauthorized
                resp_wrong_token = client.post(
                    "/v1/convert",
                    files={"file": ("sample.txt", f, "text/plain")},
                    headers={"X-API-Token": "wrong_token"},
                )
                self.assertEqual(resp_wrong_token.status_code, 401)

            with open(txt_file, "rb") as f:
                # 3. Truyền đúng qua X-API-Token -> 200 OK
                resp_correct = client.post(
                    "/v1/convert",
                    files={"file": ("sample.txt", f, "text/plain")},
                    headers={"X-API-Token": "test_secure_token_999"},
                )
                self.assertEqual(resp_correct.status_code, 200)

            with open(txt_file, "rb") as f:
                # 4. Truyền đúng qua Authorization: Bearer -> 200 OK
                resp_bearer = client.post(
                    "/v1/convert",
                    files={"file": ("sample.txt", f, "text/plain")},
                    headers={"Authorization": "Bearer test_secure_token_999"},
                )
                self.assertEqual(resp_bearer.status_code, 200)

            # 5. Endpoint /health luôn public không cần token -> 200 OK
            health_resp = client.get("/health")
            self.assertEqual(health_resp.status_code, 200)

            # 6. Kiểm tra Swagger /openapi.json tự động kích hoạt nút Authorize (BearerAuth & ApiKeyAuth)
            app.openapi_schema = None
            schema_resp = client.get("/openapi.json")
            self.assertEqual(schema_resp.status_code, 200)
            schema = schema_resp.json()
            self.assertIn("securitySchemes", schema["components"])
            self.assertIn("BearerAuth", schema["components"]["securitySchemes"])
            self.assertIn("ApiKeyAuth", schema["components"]["securitySchemes"])
            self.assertIn("security", schema["paths"]["/v1/convert"]["post"])
        finally:
            settings.API_AUTH_TOKEN = original_token
            app.openapi_schema = None

            # 7. Khi không có token, Swagger tự động ẩn nút Authorize và xóa security
            if not original_token:
                reset_schema = client.get("/openapi.json").json()
                self.assertNotIn("securitySchemes", reset_schema.get("components", {}))
                self.assertNotIn("security", reset_schema["paths"]["/v1/convert"]["post"])


if __name__ == "__main__":
    unittest.main()
