from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OCRInfo(BaseModel):
    model: str | None = None
    prompt_tokens: int = Field(0, description="Số lượng request tokens (prompt tokens)")
    completion_tokens: int = Field(0, description="Số lượng response tokens (completion tokens)")
    total_tokens: int = Field(0, description="Tổng số tokens sử dụng")
    call_count: int = Field(0, description="Số lần gọi LLM Vision OCR")


class ConversionResult(BaseModel):
    markdown: str
    char_count: int
    title: str | None = None
    ocr: OCRInfo | None = None


class SyncConvertResponse(BaseModel):
    status: str = "success"
    filename: str
    result: ConversionResult
    duration_seconds: float


class AsyncConvertResponse(BaseModel):
    status: str = "queued"
    task_id: str
    message: str = "Tác vụ đã được đưa vào hàng đợi xử lý."


class ErrorDetail(BaseModel):
    code: str
    message: str


class TaskMetrics(BaseModel):
    queued_at: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    filename: str
    result: ConversionResult | None = None
    error: ErrorDetail | None = None
    custom_metadata: dict[str, Any] | None = None
    metrics: TaskMetrics | None = None


class WebhookPayload(BaseModel):
    event: str  # task.completed or task.failed
    task_id: str
    status: TaskStatus
    filename: str
    result: ConversionResult | None = None
    error: ErrorDetail | None = None
    custom_metadata: dict[str, Any] | None = None
    metrics: TaskMetrics | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    plugins_enabled: bool
    redis_connected: bool | None = None

