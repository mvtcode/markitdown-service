from datetime import datetime, timezone
import logging
import os
import time
from typing import Any

from markitdown_service.converter import DocumentConverterService
from markitdown_service.llm_factory import LLMConfig
from markitdown_service.queue.celery_app import celery_app
from markitdown_service.queue.storage import save_task_state, get_task_state
from markitdown_service.queue.webhook import send_webhook_notification_sync
from markitdown_service.schemas import TaskStatus

logger = logging.getLogger(__name__)


def execute_conversion(
    task_id: str,
    file_path: str,
    filename: str,
    llm_config_dict: dict[str, Any] | None,
    callback_url: str | None = None,
    callback_secret: str | None = None,
    callback_headers: dict[str, str] | None = None,
    custom_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Core execution logic for background conversion task.
    Usable by Celery worker and FastAPI background tasks.
    """
    logger.info(f"Starting conversion for task {task_id} (file: {filename})")
    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.time()

    # Load existing state or initialize
    state = get_task_state(task_id) or {
        "task_id": task_id,
        "filename": filename,
        "custom_metadata": custom_metadata,
        "metrics": {"queued_at": started_at},
    }

    state["status"] = TaskStatus.PROCESSING.value
    state.setdefault("metrics", {})["started_at"] = started_at
    save_task_state(task_id, state)

    llm_config = LLMConfig(
        api_key=llm_config_dict.get("api_key") if llm_config_dict else None,
        base_url=llm_config_dict.get("base_url") if llm_config_dict else None,
        model=llm_config_dict.get("model") if llm_config_dict else None,
        prompt=llm_config_dict.get("prompt") if llm_config_dict else None,
    )

    try:
        # Perform MarkItDown conversion
        conv_result = DocumentConverterService.convert_file(file_path, llm_config)
        duration = round(time.time() - start_time, 2)
        completed_at = datetime.now(timezone.utc).isoformat()

        state["status"] = TaskStatus.COMPLETED.value
        state["result"] = conv_result.model_dump()
        state["metrics"]["completed_at"] = completed_at
        state["metrics"]["duration_seconds"] = duration
        save_task_state(task_id, state)
        logger.info(f"Task {task_id} completed successfully in {duration}s")

        # Prepare webhook payload
        if callback_url:
            webhook_payload = {
                "event": "task.completed",
                "task_id": task_id,
                "status": TaskStatus.COMPLETED.value,
                "filename": filename,
                "result": conv_result.model_dump(),
                "custom_metadata": custom_metadata,
                "metrics": state["metrics"],
            }
            send_webhook_notification_sync(
                callback_url=callback_url,
                payload=webhook_payload,
                secret=callback_secret,
                custom_headers=callback_headers,
            )

    except Exception as e:
        duration = round(time.time() - start_time, 2)
        completed_at = datetime.now(timezone.utc).isoformat()
        logger.exception(f"Task {task_id} failed: {e}")

        state["status"] = TaskStatus.FAILED.value
        state["error"] = {
            "code": "CONVERSION_ERROR",
            "message": str(e),
        }
        state["metrics"]["completed_at"] = completed_at
        state["metrics"]["duration_seconds"] = duration
        save_task_state(task_id, state)

        if callback_url:
            webhook_payload = {
                "event": "task.failed",
                "task_id": task_id,
                "status": TaskStatus.FAILED.value,
                "filename": filename,
                "error": state["error"],
                "custom_metadata": custom_metadata,
                "metrics": state["metrics"],
            }
            send_webhook_notification_sync(
                callback_url=callback_url,
                payload=webhook_payload,
                secret=callback_secret,
                custom_headers=callback_headers,
            )

    finally:
        # Optionally cleanup temporary file if it was copied to storage
        if os.path.exists(file_path) and "storage_data" in file_path:
            try:
                os.remove(file_path)
            except Exception:
                pass

    return state


if celery_app is not None:
    @celery_app.task(name="markitdown.convert_task", bind=True)
    def celery_convert_task(
        self,
        task_id: str,
        file_path: str,
        filename: str,
        llm_config_dict: dict[str, Any] | None,
        callback_url: str | None = None,
        callback_secret: str | None = None,
        callback_headers: dict[str, str] | None = None,
        custom_metadata: dict[str, Any] | None = None,
    ):
        return execute_conversion(
            task_id=task_id,
            file_path=file_path,
            filename=filename,
            llm_config_dict=llm_config_dict,
            callback_url=callback_url,
            callback_secret=callback_secret,
            callback_headers=callback_headers,
            custom_metadata=custom_metadata,
        )
else:
    celery_convert_task = None

