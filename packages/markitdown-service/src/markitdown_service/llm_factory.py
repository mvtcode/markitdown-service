import logging
from typing import Any
from openai import OpenAI
from markitdown_service.config import settings
from markitdown_service.schemas import OCRInfo

logger = logging.getLogger(__name__)


class LLMUsageTracker:
    """Tracks token usage and model metadata across LLM Vision OCR calls."""

    def __init__(self, default_model: str | None = None):
        self.default_model = default_model
        self.model = default_model
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.call_count: int = 0

    def record_response(self, response: Any, request_model: str | None = None) -> None:
        self.call_count += 1
        if hasattr(response, "model") and response.model:
            self.model = response.model
        elif request_model:
            self.model = request_model

        usage = getattr(response, "usage", None)
        if usage:
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
            self.total_tokens += getattr(usage, "total_tokens", 0) or 0

    def to_ocr_info(self) -> OCRInfo | None:
        if self.call_count == 0:
            return None
        return OCRInfo(
            model=self.model or self.default_model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
            call_count=self.call_count,
        )


class LLMConfig:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        prompt: str | None = None,
    ):
        self.api_key = api_key or settings.DEFAULT_LLM_API_KEY
        self.base_url = base_url or settings.DEFAULT_LLM_BASE_URL
        self.model = model or settings.DEFAULT_LLM_MODEL
        self.prompt = prompt or settings.DEFAULT_LLM_PROMPT

    @property
    def has_client(self) -> bool:
        return bool(self.api_key or self.base_url)

    def create_client(self, tracker: LLMUsageTracker | None = None) -> OpenAI | None:
        if not self.has_client:
            return None

        # Some local LLM endpoints (like Ollama or vLLM) don't require an actual API key,
        # but OpenAI client requires a non-empty string.
        effective_key = self.api_key or "none"
        kwargs: dict[str, Any] = {"api_key": effective_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        try:
            client = OpenAI(**kwargs)
            if tracker is not None:
                original_create = client.chat.completions.create

                def tracked_create(*args, **kwargs):
                    resp = original_create(*args, **kwargs)
                    tracker.record_response(resp, request_model=kwargs.get("model"))
                    return resp

                client.chat.completions.create = tracked_create

            return client
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            return None


def extract_llm_config_from_headers(headers: dict[str, str] | Any) -> LLMConfig:
    """
    Extract LLM configuration from HTTP headers or dictionary.
    Supports case-insensitive header lookup.
    """
    normalized = {}
    if hasattr(headers, "items"):
        normalized = {k.lower(): v for k, v in headers.items()}

    api_key = normalized.get("x-llm-api-key")
    base_url = normalized.get("x-llm-base-url")
    model = normalized.get("x-llm-model")
    prompt = normalized.get("x-llm-prompt")

    return LLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        prompt=prompt,
    )
