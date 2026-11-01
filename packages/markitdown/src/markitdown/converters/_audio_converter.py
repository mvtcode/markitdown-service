import logging
from typing import Any, BinaryIO

from ._exiftool import exiftool_metadata
from ._transcribe_audio import transcribe_audio
from .._base_converter import DocumentConverter, DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException

logger = logging.getLogger(__name__)

ACCEPTED_MIME_TYPE_PREFIXES = [
    "audio/x-wav",
    "audio/mpeg",
    "video/mp4",
]

ACCEPTED_FILE_EXTENSIONS = [
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
]


class AudioConverter(DocumentConverter):
    """
    Converts audio files to markdown via:
    1. EXIF / ID3 metadata extraction (if `exiftool` is installed)
    2. Whisper transcription via OpenAI client (if `llm_client` is configured)
    3. Fallback speech transcription via `speech_recognition` (Google Speech)
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        md_content = ""

        # 1. Add metadata via exiftool if available
        try:
            metadata = exiftool_metadata(
                file_stream, exiftool_path=kwargs.get("exiftool_path")
            )
            if metadata:
                for f in [
                    "Title",
                    "Artist",
                    "Author",
                    "Band",
                    "Album",
                    "Genre",
                    "Track",
                    "DateTimeOriginal",
                    "CreateDate",
                    "NumChannels",
                    "SampleRate",
                    "AvgBytesPerSec",
                    "BitsPerSample",
                ]:
                    if f in metadata:
                        md_content += f"{f}: {metadata[f]}\n"
        except Exception as e:
            logger.debug(f"Exiftool metadata extraction skipped: {e}")
        finally:
            file_stream.seek(0)

        # 2. Determine audio format
        if stream_info.extension == ".wav" or stream_info.mimetype == "audio/x-wav":
            audio_format = "wav"
        elif stream_info.extension == ".mp3" or stream_info.mimetype == "audio/mpeg":
            audio_format = "mp3"
        elif (
            stream_info.extension in [".mp4", ".m4a"]
            or stream_info.mimetype == "video/mp4"
        ):
            audio_format = "mp4"
        else:
            audio_format = None

        language = kwargs.get("language")
        transcript_text = None

        # 3. Method A: High-accuracy OpenAI Whisper transcription (if llm_client is provided)
        llm_client = kwargs.get("llm_client")
        if llm_client and hasattr(llm_client, "audio") and hasattr(llm_client.audio, "transcriptions") and audio_format:
            try:
                file_stream.seek(0)
                ext = stream_info.extension or f".{audio_format}"
                filename = f"audio{ext}"
                content_type = stream_info.mimetype or f"audio/{audio_format}"
                file_data = file_stream.read()

                whisper_kwargs = {
                    "model": kwargs.get("whisper_model", "whisper-1"),
                    "file": (filename, file_data, content_type),
                }
                if language:
                    whisper_kwargs["language"] = language

                whisper_res = llm_client.audio.transcriptions.create(**whisper_kwargs)
                if whisper_res and hasattr(whisper_res, "text") and whisper_res.text:
                    transcript_text = whisper_res.text.strip()
                    logger.info("Successfully transcribed audio using OpenAI Whisper.")
            except Exception as e:
                logger.warning(f"OpenAI Whisper transcription attempt failed: {e}. Falling back to standard speech recognition.")
            finally:
                file_stream.seek(0)

        # 4. Method B: Fallback to local speech_recognition (Google Speech)
        if not transcript_text and audio_format:
            try:
                file_stream.seek(0)
                transcript_text = transcribe_audio(
                    file_stream, audio_format=audio_format, language=language or "en-US"
                )
            except MissingDependencyException:
                pass
            except Exception as e:
                logger.debug(f"Local speech recognition failed: {e}")
            finally:
                file_stream.seek(0)

        if transcript_text and transcript_text != "[No speech detected]":
            if md_content:
                md_content += "\n### Audio Transcript:\n" + transcript_text
            else:
                md_content = "### Audio Transcript:\n" + transcript_text

        # 5. Fallback placeholder if nothing was extracted
        if not md_content.strip():
            ext_label = (stream_info.extension or "audio").upper().lstrip(".")
            md_content = f"# Audio File ({ext_label})\n\n[No speech detected or audio contains no metadata]"

        return DocumentConverterResult(markdown=md_content.strip())
