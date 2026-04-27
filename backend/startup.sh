#!/bin/bash
# Azure App Service Linux startup script
set -e

echo "[startup] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq tesseract-ocr poppler-utils

echo "[startup] Running DB migrations..."
cd /home/site/wwwroot
alembic upgrade head

echo "[startup] Starting uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
