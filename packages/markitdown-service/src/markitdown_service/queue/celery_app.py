import logging
from markitdown_service.config import settings

logger = logging.getLogger(__name__)

celery_app = None

try:
    from celery import Celery

    celery_app = Celery(
        "markitdown_worker",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour max
    )

    # Auto-discover tasks
    celery_app.autodiscover_tasks(["markitdown_service.queue"])
except ImportError:
    logger.info("Celery is not installed. Running in local queue mode.")
