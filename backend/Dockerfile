FROM python:3.11-slim-bookworm

WORKDIR /app

# ── Python dependencies (cached layer) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──
COPY . .

# ── Persistent data directory for SQLite DB ──
RUN mkdir -p /home/data

# ── Environment ──
ENV DATABASE_URL=sqlite:////home/data/pkd.db

EXPOSE 8000

# ── Health check ──
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# ── Start ──
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]