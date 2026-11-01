# MarkItDown Conversion & OCR Service

[![Build Status](https://img.shields.io/badge/tests-12%20passed-brightgreen.svg)](tests/readme.md)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](docker-compose.yml)
[![Based on](https://img.shields.io/badge/upstream-microsoft%2Fmarkitdown-black.svg)](https://github.com/microsoft/markitdown)

Microservice hiệu năng cao chuyển đổi tài liệu đa định dạng sang Markdown, tích hợp **OCR thông minh qua LLM Vision**, hệ thống **hàng đợi bất đồng bộ (Queue)**, **Webhook Callback Notification** và **bảo mật API Token**. Dự án được xây dựng và mở rộng trực tiếp trên nền tảng mã nguồn gốc [microsoft/markitdown](https://github.com/microsoft/markitdown).

---

## 🌟 Tính Năng Nổi Bật

- **Hỗ trợ định dạng toàn diện:** PDF (văn bản & quét), Word (`.docx`), Excel (`.xlsx`, `.csv`), PowerPoint (`.pptx`), HTML, EPUB, hình ảnh (`.png`, `.jpg`, `.jpeg`), tệp âm thanh (`.mp3`, `.wav`, `.m4a`, `.mp4`).
- **Phiên âm âm thanh (Audio Transcription):** Tự động chuyển đổi file `.mp3`, `.wav`, `.m4a` sang văn bản với **OpenAI Whisper API** (`whisper-1`) đa ngôn ngữ (Tiếng Việt, Anh, ...) hoặc Google Speech fallback.
- **OCR thông minh bằng LLM Vision:** Tự động trích xuất chữ từ hình ảnh và trang PDF scan bằng các mô hình thị giác tiên tiến (GPT-4o, GPT-4o-mini, Gemini, Claude, Ollama...).
- **Báo cáo Token OCR chi tiết:** Mỗi phản hồi OCR đều trả về thông tin đo lường minh bạch: `prompt_tokens` (request), `completion_tokens` (response), `total_tokens`, `model` và số lần gọi.
- **Cơ chế BYOK (Bring Your Own Key):** Cho phép client truyền linh hoạt API Key, Base URL và Model qua HTTP Headers (`X-LLM-Api-Key`, `X-LLM-Base-Url`, `X-LLM-Model`).
- **Bảo mật API:** Chặn truy cập trái phép bằng header token (`X-API-Token` hoặc `Authorization: Bearer`), cấu hình qua biến môi trường `API_AUTH_TOKEN`.
- **Hai phương thức xử lý linh hoạt:**
  - **Đồng bộ (Synchronous):** `POST /v1/convert` — Nhận kết quả Markdown ngay lập tức.
  - **Bất đồng bộ (Async Queue):** `POST /v1/convert/async` — Đưa vào hàng đợi xử lý ngầm, trả về `202 Accepted` ngay.
- **Webhook Callback Notification:**
  - Tự động gửi kết quả đến `callback_url` khi hoàn tất.
  - Ký số bảo mật chuẩn **HMAC-SHA256** qua header `X-MarkItDown-Signature`.
  - Cơ chế thử lại tự động (**Exponential Backoff Retry**) tối đa 4 lần khi gặp sự cố mạng hoặc lỗi phía nhận.
  - Bảo toàn metadata nghiệp vụ của đối tác (`custom_metadata`).
- **Khả năng chịu lỗi cao:** Tự động fallback sang lưu trữ cục bộ khi chạy môi trường dev không có Redis.

---

## 🏗️ Cấu Trúc Dự Án (Monorepo)

```text
markitdown/
├── packages/
│   ├── markitdown/             # [Core Gốc] Engine chuyển đổi tài liệu của Microsoft
│   ├── markitdown-ocr/         # [Core Gốc OCR] Gói mở rộng OCR LLM Vision chính thức
│   ├── markitdown-mcp/         # [Core Gốc MCP] Máy chủ giao thức Model Context Protocol
│   └── markitdown-service/     # [Gói Dịch Vụ Mới] FastAPI, Queue, Webhooks, Auth Token & Metrics
├── tests/                      # Bộ kiểm thử tích hợp chuyên sâu (12 bài test E2E)
│   ├── fixtures/               # Dữ liệu test mẫu (TXT, CSV, DOCX, XLSX, WAV, PNG, JPG, PDF)
│   ├── generate_test_fixtures.py
│   ├── test_full_features.py
│   └── run_all_tests.py
├── Dockerfile                  # Dockerfile đa tầng cài sẵn Poppler, FFmpeg và các package nội bộ
├── docker-compose.yml          # Triển khai đồng bộ: API + Celery Worker + Redis
├── .env.example                # Mẫu biến môi trường
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### Cách 1: Khởi chạy bằng Docker Compose (Khuyến nghị cho Production)

```bash
# 1. Sao chép tệp cấu hình môi trường
cp .env.example .env

# 2. Khởi chạy toàn bộ hệ sinh thái (API + Celery Worker + Redis)
docker-compose up --build -d

# 3. Kiểm tra logs
docker-compose logs -f
```

- **Swagger UI Documentation:** `http://localhost:8000/docs`
- **Healthcheck:** `GET http://localhost:8000/health`

---

### Cách 2: Khởi chạy Cục Bộ (Local Development)

#### 1. Yêu cầu hệ thống:

- Python 3.10+
- (Tùy chọn) Redis Server (nếu không có, hệ thống tự động chạy chế độ fallback cục bộ).

#### 2. Cài đặt môi trường:

```bash
# Cài đặt các thư viện cần thiết
pip install fastapi uvicorn[standard] python-multipart pydantic pydantic-settings httpx openai redis celery mammoth openpyxl pdfminer.six pdfplumber pillow
```

#### 3. Khởi chạy Server:

```bash
# Trên Windows PowerShell:
$env:PYTHONPATH=".;packages/markitdown/src;packages/markitdown-ocr/src;packages/markitdown-service/src"
uvicorn markitdown_service.app:app --host 0.0.0.0 --port 8000 --reload

# Trên Linux / macOS:
PYTHONPATH=".:packages/markitdown/src:packages/markitdown-ocr/src:packages/markitdown-service/src" \
uvicorn markitdown_service.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## ⚙️ Cấu Hình Biến Môi Trường (`.env`)

| Biến Môi Trường        |          Mặc Định          | Mô Tả                                                                             |
| :--------------------- | :------------------------: | :-------------------------------------------------------------------------------- |
| `API_AUTH_TOKEN`       |         _(Trống)_          | Token bảo vệ API. Nếu để trống, API sẽ ở chế độ công khai (public).               |
| `DEFAULT_LLM_API_KEY`  |         _(Trống)_          | Khóa API mặc định cho OCR (ví dụ: `sk-proj-...`).                                 |
| `DEFAULT_LLM_BASE_URL` |         _(Trống)_          | Endpoint tương thích OpenAI (OpenAI: để trống; Gemini/Ollama: điền URL).          |
| `DEFAULT_LLM_MODEL`    |          `gpt-4o`          | Tên mô hình thị giác mặc định dùng cho OCR (`gpt-4o`, `gpt-4o-mini`).             |
| `REDIS_URL`            | `redis://localhost:6379/0` | Địa chỉ kết nối Redis Message Broker.                                             |
| `QUEUE_MODE`           |          `celery`          | Chế độ hàng đợi (`celery` cho worker phân tán, hoặc `local` cho single instance). |
| `STORAGE_DIR`          |      `./storage_data`      | Thư mục lưu trữ tạm file tải lên cho queue.                                       |
| `WEBHOOK_MAX_RETRIES`  |            `4`             | Số lần thử lại tối đa khi webhook callback gặp sự cố.                             |

---

## 📖 Hướng Dẫn Sử Dụng API Chi Tiết

### 1. Xác thực (Authentication)

Nếu server cấu hình `API_AUTH_TOKEN`, mọi request đến các endpoint `/v1/*` cần truyền header:

- `X-API-Token: <token>` hoặc
- `Authorization: Bearer <token>`

---

### 2. Chuyển đổi Đồng bộ (Synchronous) — `POST /v1/convert`

Chuyển đổi tức thì các tệp tin nhẹ (Word, Excel, PDF có text, Ảnh nhỏ) và nhận kết quả ngay trong HTTP Response.

```bash
curl -X POST "http://localhost:8000/v1/convert" \
  -H "X-API-Token: your-secret-api-token" \
  -H "X-LLM-Api-Key: sk-your-llm-key" \
  -H "X-LLM-Model: gpt-4o" \
  -F "file=@receipt.png"
```

#### Phản hồi mẫu khi có OCR LLM:

```json
{
  "status": "success",
  "filename": "receipt.png",
  "result": {
    "markdown": "# HÓA ĐƠN BÁN HÀNG\n\n- Khách hàng: Nguyễn Văn A\n- Tổng tiền: 5.000.000 VND",
    "char_count": 128,
    "title": "HÓA ĐƠN BÁN HÀNG",
    "ocr": {
      "model": "gpt-4o",
      "prompt_tokens": 850,
      "completion_tokens": 45,
      "total_tokens": 895,
      "call_count": 1
    }
  },
  "duration_seconds": 1.42
}
```

_(Lưu ý: Đối với các tệp văn bản thuần không cần gọi OCR, trường `ocr` sẽ là `null`)_.

---

### 3. Chuyển đổi Bất đồng bộ qua Hàng đợi — `POST /v1/convert/async`

Dành cho các tệp nặng, PDF scan nhiều trang hoặc hệ thống phân tán cần xếp hàng và nhận thông báo kết quả chủ động.

```bash
curl -X POST "http://localhost:8000/v1/convert/async" \
  -H "X-API-Token: your-secret-api-token" \
  -H "X-LLM-Api-Key: sk-your-llm-key" \
  -F "file=@heavy_contract.pdf" \
  -F "callback_url=https://your-domain.com/api/webhook" \
  -F "callback_secret=my_secret_signing_key_2026" \
  -F "custom_metadata={\"contract_id\": \"CTR-9988\", \"created_by\": \"admin\"}"
```

#### Phản hồi tức thì (`202 Accepted`):

```json
{
  "status": "queued",
  "task_id": "48fdc5bf-9f84-4d24-982d-700e478d7f22",
  "message": "Tác vụ đã được đưa vào hàng đợi xử lý."
}
```

---

### 4. Cơ chế Webhook Callback Notification

Khi Worker xử lý xong, hệ thống sẽ thực hiện một request `POST` đến `callback_url` với các header bảo mật:

```http
Content-Type: application/json
X-MarkItDown-Event: task.completed
X-MarkItDown-Task-Id: 48fdc5bf-9f84-4d24-982d-700e478d7f22
X-MarkItDown-Signature: sha256=d38f8... (Chữ ký HMAC-SHA256 tính từ body và callback_secret)
```

#### Payload Callback gửi về bên ngoài:

```json
{
  "event": "task.completed",
  "task_id": "48fdc5bf-9f84-4d24-982d-700e478d7f22",
  "status": "completed",
  "filename": "heavy_contract.pdf",
  "result": {
    "markdown": "# HỢP ĐỒNG KINH TẾ...",
    "char_count": 8420,
    "title": "HỢP ĐỒNG KINH TẾ",
    "ocr": {
      "model": "gpt-4o",
      "prompt_tokens": 1250,
      "completion_tokens": 120,
      "total_tokens": 1370,
      "call_count": 2
    }
  },
  "custom_metadata": {
    "contract_id": "CTR-9988",
    "created_by": "admin"
  },
  "metrics": {
    "queued_at": "2026-11-01T11:20:00Z",
    "started_at": "2026-11-01T11:20:01Z",
    "completed_at": "2026-11-01T11:20:15Z",
    "duration_seconds": 14.1
  }
}
```

---

### 5. Tra cứu trạng thái Task (Fallback Polling) — `GET /v1/tasks/{task_id}`

```bash
curl -X GET "http://localhost:8000/v1/tasks/48fdc5bf-9f84-4d24-982d-700e478d7f22" \
  -H "X-API-Token: your-secret-api-token"
```

---

## 🧪 Kiểm Thử Tự Động (Test Suite)

Dự án tích hợp bộ kiểm thử 11 kịch bản End-to-End từ văn bản thuần, media, OCR ảnh đến luồng Webhook HMAC thực tế:

```powershell
# Chạy toàn bộ bài test:
$env:PYTHONPATH=".;packages/markitdown/src;packages/markitdown-ocr/src;packages/markitdown-service/src"
python tests/run_all_tests.py
```

Xem tài liệu chi tiết về kiểm thử tại: [tests/readme.md](tests/readme.md).

---

## 👨‍💻 Tác Giả & Bản Quyền

- **Tác giả:** **[Mạc Tân](https://www.facebook.com/mvt.hp.star/)**
- **Hotline / Zalo:** [0964 335 688](tel:0964335688)
- **Mã nguồn:** Mã nguồn mở phục vụ nghiên cứu, học tập và ứng dụng thực tế trên các dòng vi điều khiển ESP32 / ESP8266 / Arduino.

⭐ _Nếu thấy kho dự án hữu ích, hãy tặng 1 Star trên GitHub để ủng hộ tác giả nhé!_

Dự án được phân phối theo giấy phép [MIT License](LICENSE).
Mã nguồn cốt lõi dựa trên dự án mã nguồn mở [Microsoft MarkItDown](https://github.com/microsoft/markitdown).
