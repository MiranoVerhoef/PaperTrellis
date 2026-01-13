# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY docs /app/docs
COPY README.md /app/README.md
COPY LICENSE /app/LICENSE

EXPOSE 8000

ENV ODM_DATA_DIR=/data \
    ODM_CONFIG_DIR=/data/config \
    ODM_INGEST_DIR=/data/ingest \
    ODM_LIBRARY_DIR=/data/library \
    ODM_FAILED_DIR=/data/failed \
    ODM_TMP_DIR=/data/tmp \
    ODM_SCAN_ENABLED=true \
    ODM_SCAN_INTERVAL_SECONDS=15 \
    ODM_TESSERACT_LANG=eng \
    ODM_AUTH_ENABLED=true

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
