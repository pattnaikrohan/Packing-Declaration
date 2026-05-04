FROM python:3.11-slim

# ── System dependencies (Tesseract OCR + Poppler for PDF → image) ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies (cached layer) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──
COPY . .

# ── Persistent data directory for SQLite DB ──
RUN mkdir -p /home/data

# ── Environment ──
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV DATABASE_URL=sqlite:////home/data/pkd.db

EXPOSE 8000

# ── Health check ──
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Start ──
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]