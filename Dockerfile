FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EXIFTOOL_PATH=/usr/bin/exiftool \
    FFMPEG_PATH=/usr/bin/ffmpeg \
    MARKITDOWN_ENABLE_PLUGINS=True \
    ORT_DISABLE_TELEMETRY=1

# Install system dependencies (ffmpeg for audio, exiftool for metadata, poppler for PDF rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libimage-exiftool-perl \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy monorepo packages
COPY packages /app/packages

# Install core markitdown, markitdown-ocr, and markitdown-service
RUN pip install --no-cache-dir \
    /app/packages/markitdown[all] \
    /app/packages/markitdown-ocr \
    /app/packages/markitdown-service

# Create directories for storage and set permissions
RUN mkdir -p /app/storage_data && chmod 777 /app/storage_data

EXPOSE 8000

# Default command runs the FastAPI server
CMD ["uvicorn", "markitdown_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
