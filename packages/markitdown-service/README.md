# MarkItDown Service

Microservice HTTP REST API & Async Queue cho [MarkItDown](https://github.com/microsoft/markitdown) hỗ trợ:
- Chuyển đổi đa định dạng tệp sang Markdown (PDF, Word, Excel, PPTX, HTML, Audio...).
- Tích hợp OCR thông minh qua LLM Vision (`markitdown-ocr`).
- Hỗ trợ BYOK (Bring Your Own Key) qua HTTP Headers.
- Xử lý đồng bộ (`POST /v1/convert`) và bất đồng bộ qua Queue (`POST /v1/convert/async`).
- Thông báo tự động qua Webhook Callback có xác thực HMAC-SHA256 và Exponential Backoff Retry.

