#!/bin/bash
# Azure App Service startup script for PKD Validator (pure Python, no system deps)
set -e

echo "=== PKD Backend Startup ==="

# Ensure persistent data directory
mkdir -p /home/data

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
