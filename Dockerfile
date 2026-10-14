# ==========================================================
# Tata Group AI Legal Document Intelligence System
# Production image — includes tesseract OCR + all parsers
# ==========================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages:
#  - tesseract-ocr: OCR engine used by pytesseract (image + scanned PDF)
#  - tesseract-ocr-eng: English language data (add more langs if needed)
#  - libglib2.0-0 / libgl1: runtime libs for Pillow & pypdfium2 image rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Persistent data location (mount a Render Disk at /data to keep data across deploys)
RUN mkdir -p /data/uploads
ENV DB_PATH=/data/legal_intelligence.db \
    UPLOAD_DIR=/data/uploads \
    AI_MODE=offline

EXPOSE 8000

# Render provides $PORT (default 10000); fall back to 8000 for local docker run
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
