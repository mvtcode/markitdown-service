import json
import logging
import os
from pathlib import Path
from typing import Any

from markitdown_service.config import settings

logger = logging.getLogger(__name__)

# In-memory / file-based cache fallback
_memory_cache: dict[str, dict[str, Any]] = {}
_redis_client = None
_redis_checked = False


def get_redis_client():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    if settings.QUEUE_MODE == "local":
        _redis_checked = True
        return None

    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        _redis_client = client
        _redis_checked = True
        return _redis_client
    except Exception as e:
        logger.info(f"Redis not reachable at {settings.REDIS_URL} ({e}). Running with local storage fallback.")
        _redis_checked = True
        return None


def get_task_file_path(task_id: str) -> Path:
    return Path(settings.STORAGE_DIR) / f"task_{task_id}.json"


def save_task_state(task_id: str, data: dict[str, Any]) -> None:
    """Save task state to Redis with TTL, or fallback to local disk and memory."""
    payload = json.dumps(data, ensure_ascii=False)
    client = get_redis_client()
    if client:
        try:
            client.set(f"task:{task_id}", payload, ex=settings.TASK_TTL_SECONDS)
            return
        except Exception as e:
            logger.warning(f"Redis set failed for task:{task_id}: {e}")

    # Fallback: in-memory and disk
    _memory_cache[task_id] = data
    try:
        task_file = get_task_file_path(task_id)
        with open(task_file, "w", encoding="utf-8") as f:
            f.write(payload)
    except Exception as e:
        logger.error(f"Failed to persist task file for {task_id}: {e}")


def get_task_state(task_id: str) -> dict[str, Any] | None:
    """Retrieve task state from Redis, or fallback to memory / disk."""
    client = get_redis_client()
    if client:
        try:
            val = client.get(f"task:{task_id}")
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning(f"Redis get failed for task:{task_id}: {e}")

    # Fallback to memory
    if task_id in _memory_cache:
        return _memory_cache[task_id]

    # Fallback to disk
    task_file = get_task_file_path(task_id)
    if task_file.exists():
        try:
            with open(task_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _memory_cache[task_id] = data
                return data
        except Exception as e:
            logger.error(f"Failed to read task file for {task_id}: {e}")

    return None

