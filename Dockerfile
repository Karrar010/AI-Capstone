# Lab 9: reproducible container (Linux; secrets injected at runtime via Compose/env).
# Base: python:3.12-slim-bookworm — small, glibc-based, good wheel support for faiss-cpu / numpy.
# Layer order: apt deps → pip install (cached when requirements.txt unchanged) → copy source last
# so code edits do not invalidate dependency layers.

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_DEFAULT_TIMEOUT=900

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only PyTorch first: avoids the huge CUDA wheel stack (~GiB) on Linux and cuts download size.
# Slow networks: high timeout + retries (default pip timeout often fails mid-download).
RUN pip install --no-cache-dir --retries 15 --default-timeout=900 \
    torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --retries 15 --default-timeout=900 -r requirements.txt

COPY . .

RUN mkdir -p /data/faiss_index \
    && useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && chown -R appuser:appuser /app /data

USER appuser

# Writable FAISS dir (volume mount in Compose). Checkpoint uses Postgres when POSTGRES_URI is set.
ENV FAISS_INDEX_PATH=/data/faiss_index \
    DOMAIN_DOCS_DIR=/app/domain_docs \
    BWA_EVAL_SKIP_SAVE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
