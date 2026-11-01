import logging
import os
import re
from pathlib import Path
from typing import BinaryIO

from markitdown import MarkItDown
from markitdown_service.llm_factory import LLMConfig, LLMUsageTracker
from markitdown_service.schemas import ConversionResult

logger = logging.getLogger(__name__)


def _extract_title_from_markdown(markdown: str) -> str | None:
    """Extract first top-level heading (# Title) from markdown if present."""
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


class DocumentConverterService:
    """Service layer coordinating MarkItDown conversion with dynamic LLM configuration."""

    @staticmethod
    def create_markitdown_instance(
        llm_config: LLMConfig,
        tracker: LLMUsageTracker | None = None,
    ) -> MarkItDown:
        """
        Instantiate MarkItDown with enabled plugins (markitdown-ocr)
        and configured LLM client with usage tracking.
        """
        client = llm_config.create_client(tracker=tracker)
        kwargs = {
            "enable_plugins": True,
        }
        if client:
            kwargs["llm_client"] = client
            kwargs["llm_model"] = llm_config.model
            if llm_config.prompt:
                kwargs["llm_prompt"] = llm_config.prompt

        return MarkItDown(**kwargs)

    @classmethod
    def convert_file(cls, file_path: str | Path, llm_config: LLMConfig) -> ConversionResult:
        """
        Convert file on disk to Markdown using MarkItDown and record OCR usage metrics if used.
        """
        path_str = str(file_path)
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"File not found: {path_str}")

        tracker = LLMUsageTracker(default_model=llm_config.model)
        md = cls.create_markitdown_instance(llm_config, tracker=tracker)
        logger.info(f"Converting file: {path_str} with model: {llm_config.model if llm_config.has_client else 'None'}")

        result = md.convert(path_str)
        text_content = result.text_content or ""
        title = result.title or _extract_title_from_markdown(text_content)
        ocr_info = tracker.to_ocr_info()

        return ConversionResult(
            markdown=text_content,
            char_count=len(text_content),
            title=title,
            ocr=ocr_info,
        )

    @classmethod
    def convert_stream(
        cls,
        stream: BinaryIO,
        llm_config: LLMConfig,
        file_extension: str | None = None,
        mimetype: str | None = None,
    ) -> ConversionResult:
        """
        Convert a binary stream to Markdown using MarkItDown.
        """
        tracker = LLMUsageTracker(default_model=llm_config.model)
        md = cls.create_markitdown_instance(llm_config, tracker=tracker)
        kwargs = {}
        if file_extension:
            kwargs["file_extension"] = file_extension
        if mimetype:
            kwargs["mimetype"] = mimetype

        result = md.convert_stream(stream, **kwargs)
        text_content = result.text_content or ""
        title = result.title or _extract_title_from_markdown(text_content)
        ocr_info = tracker.to_ocr_info()

        return ConversionResult(
            markdown=text_content,
            char_count=len(text_content),
            title=title,
            ocr=ocr_info,
        )
