from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from markitdown import MarkItDown
from markitdown_service.__about__ import __version__
from markitdown_service.config import settings
from markitdown_service.converter import DocumentConverterService
from markitdown_service.llm_factory import extract_llm_config_from_headers
from markitdown_service.queue.celery_app import celery_app
from markitdown_service.queue.storage import get_redis_client, get_task_state, save_task_state
from markitdown_service.queue.tasks import celery_convert_task, execute_conversion
from markitdown_service.schemas import (
    AsyncConvertResponse,
    HealthResponse,
    SyncConvertResponse,
    TaskStatus,
    TaskStatusResponse,
)

logger = logging.getLogger("markitdown_service")
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)

app = FastAPI(
    title="MarkItDown Conversion & OCR Service",
    description=(
        "Microservice chuyển đổi đa định dạng tài liệu sang Markdown với hỗ trợ LLM Vision OCR, "
        "Dynamic LLM Keys (BYOK), xử lý hàng đợi (Queue) và thông báo kết quả qua Webhook Callback."
    ),
    version=__version__,
)

# Enable CORS for external web integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_token(
    request: Request,
    api_token_header: str | None = Security(api_key_header),
    auth_credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
):
    """
    Xác thực API Token khi biến môi trường API_AUTH_TOKEN được thiết lập.
    Hỗ trợ:
      - Header: X-API-Token: <token>
      - Header: X-API-Key: <token>
      - Header: Authorization: Bearer <token>
    """
    if not settings.API_AUTH_TOKEN:
        return True

    expected = settings.API_AUTH_TOKEN.strip()

    # Kiểm tra X-API-Token
    if api_token_header and api_token_header.strip() == expected:
        return True

    # Kiểm tra X-API-Key
    alt_token = request.headers.get("x-api-key")
    if alt_token and alt_token.strip() == expected:
        return True

    # Kiểm tra Authorization: Bearer <token>
    if auth_credentials and auth_credentials.credentials.strip() == expected:
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Token xác thực API không hợp lệ hoặc bị thiếu (X-API-Token hoặc Authorization: Bearer).",
    )


def custom_openapi():
    """
    Tùy biến OpenAPI Schema:
    - Khi có API_AUTH_TOKEN: Hiển thị nút "Authorize" (Bearer & X-API-Token) trên Swagger UI và biểu tượng khóa 🔒 trên các endpoint /v1/*.
    - Khi không có API_AUTH_TOKEN: Tự động ẩn hoàn toàn nút "Authorize" và biểu tượng khóa để Swagger ở chế độ Public.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    if settings.API_AUTH_TOKEN and settings.API_AUTH_TOKEN.strip():
        # Đăng ký Security Schemes để Swagger UI hiển thị modal "Authorize"
        openapi_schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "Token",
                "description": "Nhập API Token bảo mật của bạn (Bearer Token)",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Token",
                "description": "Hoặc truyền Token qua header X-API-Token",
            },
        }

        # Áp dụng yêu cầu xác thực lên tất cả các route /v1/*
        for path, path_item in openapi_schema.get("paths", {}).items():
            if path.startswith("/v1/"):
                for method in path_item:
                    if method.lower() in ["get", "post", "put", "delete", "patch"]:
                        path_item[method]["security"] = [
                            {"BearerAuth": []},
                            {"ApiKeyAuth": []},
                        ]
    else:
        # Nếu không cấu hình API_AUTH_TOKEN, gỡ bỏ toàn bộ security schemes để Swagger hiển thị public
        if "components" in openapi_schema and "securitySchemes" in openapi_schema["components"]:
            del openapi_schema["components"]["securitySchemes"]
        for path, path_item in openapi_schema.get("paths", {}).items():
            for method in path_item:
                if isinstance(path_item[method], dict) and "security" in path_item[method]:
                    del path_item[method]["security"]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Kiểm tra sức khỏe hệ thống và trạng thái kết nối Redis."""
    redis_connected = False
    try:
        client = get_redis_client()
        if client:
            redis_connected = bool(client.ping())
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        version=__version__,
        plugins_enabled=True,
        redis_connected=redis_connected,
    )


@app.post(
    "/v1/convert",
    response_model=SyncConvertResponse,
    dependencies=[Depends(verify_api_token)],
    tags=["Conversion"],
    summary="Chuyển đổi tài liệu đồng bộ (Sync)",
)
async def convert_sync(
    request: Request,
    file: UploadFile = File(..., description="File tài liệu cần convert (PDF, DOCX, XLSX, Image...)"),
):
    """
    Chuyển đổi file sang Markdown ngay lập tức và trả về kết quả trong HTTP response.
    Phù hợp cho các file tài liệu dung lượng nhỏ đến trung bình.
    """
    filename = file.filename or "unknown"
    start_time = time.time()
    llm_config = extract_llm_config_from_headers(request.headers)

    # Validate file extension
    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        # Stream file content to temp disk to avoid large memory spikes
        shutil.copyfileobj(file.file, tmp)
    
    # tmp is now closed, safe for Windows file operations
    try:
        file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        if file_size_mb > settings.MAX_SYNC_FILE_SIZE_MB:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Kích thước file ({file_size_mb:.1f}MB) vượt quá giới hạn xử lý đồng bộ "
                    f"({settings.MAX_SYNC_FILE_SIZE_MB}MB). Vui lòng sử dụng POST /v1/convert/async."
                ),
            )

        # Convert using Core Engine
        result = DocumentConverterService.convert_file(tmp_path, llm_config)
        duration = round(time.time() - start_time, 2)

        return SyncConvertResponse(
            status="success",
            filename=filename,
            result=result,
            duration_seconds=duration,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Conversion error for {filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi chuyển đổi tài liệu: {str(e)}",
        )
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.post(
    "/v1/convert/async",
    response_model=AsyncConvertResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_token)],
    tags=["Conversion"],
    summary="Chuyển đổi tài liệu qua Hàng đợi (Queue) có Webhook",
)
async def convert_async(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File tài liệu cần convert"),
    callback_url: str | None = Form(None, description="URL Webhook nhận kết quả khi hoàn tất"),
    callback_secret: str | None = Form(None, description="Secret token tạo chữ ký HMAC-SHA256"),
    callback_headers: str | None = Form(None, description="JSON string các header gửi kèm webhook"),
    custom_metadata: str | None = Form(None, description="JSON string metadata nghiệp vụ trả về trong callback"),
):
    """
    Đưa file vào hàng đợi xử lý bất đồng bộ.
    Khi xử lý xong (thành công hoặc thất bại), hệ thống sẽ chủ động gửi kết quả
    về callback_url kèm chữ ký HMAC xác thực.
    """
    task_id = str(uuid.uuid4())
    filename = file.filename or "unknown"
    llm_config = extract_llm_config_from_headers(request.headers)

    # Parse JSON form parameters safely
    parsed_callback_headers = None
    if callback_headers:
        try:
            parsed_callback_headers = json.loads(callback_headers)
        except Exception:
            raise HTTPException(status_code=400, detail="callback_headers phải là JSON string hợp lệ.")

    parsed_metadata = None
    if custom_metadata:
        try:
            parsed_metadata = json.loads(custom_metadata)
        except Exception:
            raise HTTPException(status_code=400, detail="custom_metadata phải là JSON string hợp lệ.")

    # Save uploaded file to persistent storage volume
    suffix = Path(filename).suffix
    saved_file_path = os.path.join(settings.STORAGE_DIR, f"{task_id}{suffix}")

    try:
        with open(saved_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Không thể lưu trữ tệp tin tải lên.")

    # Check file size limit for async
    file_size_mb = os.path.getsize(saved_file_path) / (1024 * 1024)
    if file_size_mb > settings.MAX_ASYNC_FILE_SIZE_MB:
        if os.path.exists(saved_file_path):
            os.remove(saved_file_path)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dung lượng tệp ({file_size_mb:.1f}MB) vượt quá giới hạn tối đa ({settings.MAX_ASYNC_FILE_SIZE_MB}MB).",
        )

    # Initialize task state in storage
    now_iso = datetime.now(timezone.utc).isoformat()
    initial_state = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "filename": filename,
        "custom_metadata": parsed_metadata,
        "metrics": {"queued_at": now_iso},
    }
    save_task_state(task_id, initial_state)

    llm_dict = {
        "api_key": llm_config.api_key,
        "base_url": llm_config.base_url,
        "model": llm_config.model,
        "prompt": llm_config.prompt,
    }

    # Dispatch to Queue
    dispatched = False
    if settings.QUEUE_MODE == "celery" and celery_convert_task is not None:
        try:
            celery_convert_task.delay(
                task_id=task_id,
                file_path=saved_file_path,
                filename=filename,
                llm_config_dict=llm_dict,
                callback_url=callback_url,
                callback_secret=callback_secret,
                callback_headers=parsed_callback_headers,
                custom_metadata=parsed_metadata,
            )
            dispatched = True
            logger.info(f"Task {task_id} successfully queued to Celery.")
        except Exception as e:
            logger.warning(f"Could not dispatch to Celery broker ({e}). Fallback to local background tasks.")

    if not dispatched:
        # Fallback / Local mode
        background_tasks.add_task(
            execute_conversion,
            task_id=task_id,
            file_path=saved_file_path,
            filename=filename,
            llm_config_dict=llm_dict,
            callback_url=callback_url,
            callback_secret=callback_secret,
            callback_headers=parsed_callback_headers,
            custom_metadata=parsed_metadata,
        )
        logger.info(f"Task {task_id} queued to FastAPI background tasks.")

    return AsyncConvertResponse(
        status="queued",
        task_id=task_id,
        message="Tác vụ đã được đưa vào hàng đợi xử lý.",
    )


@app.get(
    "/v1/tasks/{task_id}",
    response_model=TaskStatusResponse,
    dependencies=[Depends(verify_api_token)],
    tags=["Conversion"],
    summary="Tra cứu trạng thái hoặc lấy kết quả Task",
)
def get_task(task_id: str):
    """
    Tra cứu trạng thái và nhận kết quả chuyển đổi của một tác vụ trong hàng đợi.
    Kết quả được lưu trữ tạm thời trong vòng 24 giờ.
    """
    state = get_task_state(task_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy thông tin cho task_id: {task_id}",
        )
    return state

