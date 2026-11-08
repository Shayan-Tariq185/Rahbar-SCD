FROM python:3.12.7-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies for document extraction and OCR, update OS packages, then clean apt cache
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends tesseract-ocr poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user with UID 10001
RUN useradd -u 10001 -r -s /bin/false -d /app appuser

WORKDIR /app

# Install Python requirements from indexer directory (context is repository root)
COPY indexer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy corpus source into container (default to eval/fixtures, overridden via build-arg)
ARG CORPUS_SRC=eval/fixtures
COPY ${CORPUS_SRC} /corpus

# Copy indexer pipeline package
COPY indexer/pipeline ./pipeline

# Ensure non-root user can read corpus and application files
RUN chown -R 10001:10001 /corpus /app

ENV CORPUS_DIR=/corpus

USER 10001

CMD ["python", "-m", "pipeline.run"]

