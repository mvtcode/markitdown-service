import hashlib
import hmac
import json
import logging
import time
from typing import Any
import httpx

from markitdown_service.config import settings

logger = logging.getLogger(__name__)


def generate_hmac_signature(payload_bytes: bytes, secret: str) -> str:
    """Generate SHA256 HMAC signature for payload bytes."""
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def send_webhook_notification_sync(
    callback_url: str,
    payload: dict[str, Any],
    secret: str | None = None,
    custom_headers: dict[str, str] | None = None,
) -> bool:
    """
    Send webhook notification synchronously with exponential backoff retries.
    Suitable for Celery worker processes.
    """
    payload_json = json.dumps(payload, ensure_ascii=False)
    payload_bytes = payload_json.encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-MarkItDown-Event": payload.get("event", "task.completed"),
        "X-MarkItDown-Task-Id": payload.get("task_id", ""),
    }

    if secret:
        headers["X-MarkItDown-Signature"] = generate_hmac_signature(payload_bytes, secret)

    if custom_headers:
        headers.update(custom_headers)

    backoff_intervals = settings.WEBHOOK_RETRY_BACKOFF[: settings.WEBHOOK_MAX_RETRIES]
    attempts = len(backoff_intervals) + 1

    for attempt in range(1, attempts + 1):
        try:
            logger.info(
                f"[Webhook] Dispatching to {callback_url} for task {payload.get('task_id')} (Attempt {attempt}/{attempts})"
            )
            with httpx.Client(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                response = client.post(callback_url, content=payload_bytes, headers=headers)
                if response.status_code < 400:
                    logger.info(
                        f"[Webhook] Successfully delivered to {callback_url} (HTTP {response.status_code})"
                    )
                    return True
                else:
                    logger.warning(
                        f"[Webhook] Target returned HTTP {response.status_code} for task {payload.get('task_id')}"
                    )
        except Exception as e:
            logger.warning(f"[Webhook] Error delivering to {callback_url} (Attempt {attempt}): {e}")

        if attempt <= len(backoff_intervals):
            sleep_time = backoff_intervals[attempt - 1]
            logger.info(f"[Webhook] Backing off for {sleep_time} seconds before retry...")
            time.sleep(sleep_time)

    logger.error(f"[Webhook] Failed all {attempts} attempts to deliver webhook to {callback_url}")
    return False


async def send_webhook_notification_async(
    callback_url: str,
    payload: dict[str, Any],
    secret: str | None = None,
    custom_headers: dict[str, str] | None = None,
) -> bool:
    """
    Send webhook notification asynchronously with exponential backoff retries.
    Suitable for FastAPI background tasks.
    """
    import asyncio

    payload_json = json.dumps(payload, ensure_ascii=False)
    payload_bytes = payload_json.encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-MarkItDown-Event": payload.get("event", "task.completed"),
        "X-MarkItDown-Task-Id": payload.get("task_id", ""),
    }

    if secret:
        headers["X-MarkItDown-Signature"] = generate_hmac_signature(payload_bytes, secret)

    if custom_headers:
        headers.update(custom_headers)

    backoff_intervals = settings.WEBHOOK_RETRY_BACKOFF[: settings.WEBHOOK_MAX_RETRIES]
    attempts = len(backoff_intervals) + 1

    for attempt in range(1, attempts + 1):
        try:
            logger.info(
                f"[Webhook-Async] Dispatching to {callback_url} for task {payload.get('task_id')} (Attempt {attempt}/{attempts})"
            )
            async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                response = await client.post(callback_url, content=payload_bytes, headers=headers)
                if response.status_code < 400:
                    logger.info(
                        f"[Webhook-Async] Successfully delivered to {callback_url} (HTTP {response.status_code})"
                    )
                    return True
                else:
                    logger.warning(
                        f"[Webhook-Async] Target returned HTTP {response.status_code} for task {payload.get('task_id')}"
                    )
        except Exception as e:
            logger.warning(f"[Webhook-Async] Error delivering to {callback_url} (Attempt {attempt}): {e}")

        if attempt <= len(backoff_intervals):
            sleep_time = backoff_intervals[attempt - 1]
            logger.info(f"[Webhook-Async] Backing off for {sleep_time} seconds before retry...")
            await asyncio.sleep(sleep_time)

    logger.error(f"[Webhook-Async] Failed all {attempts} attempts to deliver webhook to {callback_url}")
    return False

