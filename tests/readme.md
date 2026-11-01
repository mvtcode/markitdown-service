# Tài Liệu Hướng Dẫn Kiểm Thử (Test Suite Documentation)

Thư mục này chứa bộ kiểm thử tích hợp chuyên sâu (Integration & End-to-End Tests) nhằm xác thực toàn diện tất cả các tính năng của **MarkItDown Conversion & OCR Service**.

---

## 1. Danh Mục Các Tính Năng Được Kiểm Thử

Bộ test kiểm tra 12 kịch bản thực tế bao phủ toàn bộ các yêu cầu kỹ thuật:

| STT | Tên Test Case | Mô tả & Định dạng kiểm thử | Kỳ vọng đầu ra |
| :---: | :--- | :--- | :--- |
| **01** | `test_01_convert_plain_text` | Upload & convert file văn bản `.txt` | Trả về `200 OK`, giữ nguyên nội dung văn bản. |
| **02** | `test_02_convert_csv` | Upload & convert bảng tính `.csv` | Tạo bảng Markdown dạng `\| Cột 1 \| Cột 2 \|`. |
| **03** | `test_03_convert_html` | Upload & convert trang `.html` | Chuyển đổi đúng heading (`#`), danh sách (`-`), thẻ `<p>`. |
| **04** | `test_04_convert_docx` | Upload & convert tài liệu Word `.docx` | Trích xuất toàn bộ tiêu đề, đoạn văn và bảng trong Word. |
| **05** | `test_05_convert_xlsx` | Upload & convert file Excel `.xlsx` | Chuyển các sheet dữ liệu sang bảng Markdown tương ứng. |
| **06** | `test_06_convert_media_audio_wav` | Upload file âm thanh `.wav` | Trích xuất metadata/audio transcript từ file WAV. |
| **06b** | `test_06b_convert_media_audio_mp3` | **Upload & transcribe âm thanh `.mp3`** | Trích xuất speech transcript bằng **OpenAI Whisper API** (`whisper-1`) hoặc Google Speech. |
| **07** | `test_07_ocr_image_png` | **OCR hình ảnh `.png` bằng LLM Vision** | Gọi OpenAI GPT-4o trích xuất đúng chữ trên hóa đơn ảnh. |
| **08** | `test_08_ocr_image_jpg` | **OCR hình ảnh `.jpg` bằng LLM Vision** | Nhận diện văn bản tiếng Việt từ ảnh nén JPEG. |
| **09** | `test_09_ocr_pdf_with_images` | **PDF kết hợp text layer và ảnh scan** | Trích xuất đồng thời text layer và vùng ảnh quét. |
| **10** | `test_10_async_queue_and_webhook` | **Queue bất đồng bộ + Webhook Callback** | - Nhận `202 Accepted` ngay khi gửi file.<br>- Background Worker xử lý ngầm.<br>- Webhook tự động bắn `POST` đến `callback_url`.<br>- Header `X-MarkItDown-Signature` khớp chuẩn **HMAC-SHA256**.<br>- Metadata nghiệp vụ (`custom_metadata`) được bảo toàn.<br>- Tra cứu được task qua `GET /v1/tasks/{task_id}`. |
| **11** | `test_11_api_token_authentication` | **Xác thực Token & Tự động ẩn/hiện Authorize Swagger** | - Chặn 401 khi thiếu/sai token.<br>- Cho phép 200 khi đúng token (Bearer / X-API-Token).<br>- Swagger tự động bật nút `Authorize 🔓` khi có cấu hình và ẩn khi public. |

---

## 2. Cấu Trúc Thư Mục Kiểm Thử

```text
tests/
├── readme.md                   # Tài liệu hướng dẫn này
├── generate_test_fixtures.py   # Script tự động tạo dữ liệu mẫu (TXT, CSV, DOCX, XLSX, WAV, ảnh OCR, PDF scan)
├── test_full_features.py       # Bộ test cases E2E hoàn chỉnh
├── run_all_tests.py            # CLI Runner tiện ích để kích hoạt toàn bộ test
└── fixtures/                   # Thư mục chứa các tệp tin test fixtures được lưu trữ và theo dõi trên Git
```

---

## 3. Hướng Dẫn Cách Chạy Test

### Cách 1: Chạy nhanh bằng Test Runner (Khuyến nghị)

Trong thư mục gốc của dự án (`d:\projects\markitdown`):

#### Trên Windows (PowerShell):
```powershell
$env:PYTHONPATH=".;packages/markitdown/src;packages/markitdown-ocr/src;packages/markitdown-service/src"
python tests/run_all_tests.py
```

#### Trên Linux / macOS (Bash):
```bash
PYTHONPATH=".:packages/markitdown/src:packages/markitdown-ocr/src:packages/markitdown-service/src" \
python tests/run_all_tests.py
```

---

### Cách 2: Chạy qua module `unittest` chuẩn của Python

Nếu muốn chạy kèm verbosity chi tiết hơn:

```powershell
$env:PYTHONPATH=".;packages/markitdown/src;packages/markitdown-ocr/src;packages/markitdown-service/src"
python -m unittest tests/test_full_features.py -v
```

---

### Cách 3: Chạy chỉ riêng một test case cụ thể

Ví dụ chỉ muốn kiểm tra riêng luồng **OCR ảnh PNG** hoặc **Async Queue + Webhook**:

```powershell
# Chỉ test OCR ảnh PNG
python -m unittest tests.test_full_features.TestMarkItDownFullFeatures.test_07_ocr_image_png -v

# Chỉ test Async Queue & Webhook Callback
python -m unittest tests.test_full_features.TestMarkItDownFullFeatures.test_10_async_queue_and_webhook_callback -v
```

---

## 4. Tự Sinh Lại Dữ Liệu Test Mẫu (Fixtures)

Bộ test có khả năng tự động sinh lại toàn bộ file mẫu nếu thư mục `tests/fixtures/` chưa tồn tại hoặc bị xóa:

```powershell
python tests/generate_test_fixtures.py
```

Các file sinh ra gồm:
* `receipt_ocr.png` / `receipt_ocr.jpg`: Tạo ảnh vẽ chữ hóa đơn thực tế bằng thư viện Pillow.
* `scanned_doc.pdf`: Tạo file PDF nhúng ảnh quét bằng PyMuPDF.
* `sample_audio.wav`: Tạo file sóng âm thanh 16kHz bằng thư viện wave chuẩn.
* `sample.docx`, `sample.xlsx`, `sample.csv`, `sample.html`, `sample.txt`.

---

## 5. Các Lưu Ý Về Môi Trường Khi Chạy Test

1. **Khóa API LLM (OpenAI / LLM Key):**
   * Các bài test OCR (test 07, 08, 09) sẽ tự động nạp `DEFAULT_LLM_API_KEY` từ tệp `.env` ở thư mục gốc.
   * Nếu có key hợp lệ, test sẽ gọi trực tiếp đến API OpenAI GPT-4o để nghiệm thu khả năng đọc chữ thực tế.
2. **Cơ chế Chịu lỗi Redis (Local Fallback):**
   * Khi chạy trực tiếp trên máy cá nhân không bật Redis Server, hệ thống sẽ tự động dùng fallback lưu trữ tạm thời (`storage_data/`), tất cả bài test vẫn đảm bảo chạy thành công 100%.
   * Khi triển khai qua Docker Compose (`docker-compose up`), hệ thống sẽ tự động kết nối với container Redis chuyên dụng.

