import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Security & API Authentication Token
    API_AUTH_TOKEN: str | None = None

    # Default LLM Fallbacks (if client does not pass headers)
    DEFAULT_LLM_API_KEY: str | None = None
    DEFAULT_LLM_BASE_URL: str | None = None
    DEFAULT_LLM_MODEL: str = "gpt-4o"
    DEFAULT_LLM_PROMPT: str | None = None

    # Storage for temporary uploaded files and async task data
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", str(Path("./storage_data").absolute()))
    TASK_TTL_SECONDS: int = 86400  # 24 hours

    # Queue configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Queue mode: 'celery' (distributed worker) or 'local' (FastAPI background tasks for single-instance)
    QUEUE_MODE: str = os.getenv("QUEUE_MODE", "celery")

    # Webhook settings
    WEBHOOK_TIMEOUT_SECONDS: float = 10.0
    WEBHOOK_MAX_RETRIES: int = 4
    # Backoff intervals in seconds: 5s, 30s, 120s, 600s
    WEBHOOK_RETRY_BACKOFF: list[float] = [5.0, 30.0, 120.0, 600.0]

    # Limits
    MAX_SYNC_FILE_SIZE_MB: int = 25
    MAX_ASYNC_FILE_SIZE_MB: int = 200


settings = Settings()

# Ensure storage directory exists
os.makedirs(settings.STORAGE_DIR, exist_ok=True)

