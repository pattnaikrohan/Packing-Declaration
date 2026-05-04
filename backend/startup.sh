#!/bin/bash
# Azure App Service Linux startup script (for non-Docker deployments)
set -e

echo "[startup] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq tesseract-ocr tesseract-ocr-eng poppler-utils

echo "[startup] Ensuring data directory exists..."
mkdir -p /home/data

echo "[startup] Installing Python dependencies..."
cd /home/site/wwwroot
pip install -r requirements.txt

echo "[startup] Starting uvicorn..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
