# PKD Validator

Biosecurity packing declaration validation system for the Australian Department of Agriculture, Fisheries and Forestry (DAFF).

---

## Quick Start (Local)

### 1. Backend

```bash
cd backend

# Copy env file
copy .env.example .env

# Create virtual environment and install dependencies
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

pip install -r requirements.txt

# Start server (DB and model_store directories auto-created)
uvicorn app.main:app --reload --port 8000
```

Backend will be available at http://localhost:8000  
API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:5173

---

## Database

**SQLite** — zero configuration. The database file is created automatically at `backend/data/pkd.db` on first startup.

No PostgreSQL, no Docker required.

---

## OCR (Optional)

OCR extraction for scanned PDFs and images requires:

**Tesseract**
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
  - Install and add to PATH, or set `TESSERACT_CMD` in `.env`
- Linux/Azure: auto-installed via startup.sh

**Poppler** (for PDF → image conversion)
- Windows: https://github.com/oschwartz10612/poppler-windows/releases
  - Extract and add the `bin/` folder to PATH
- Linux/Azure: auto-installed via startup.sh

> **Note:** OCR gracefully degrades if not installed. Digital PDF, DOCX, and XLSX files work without OCR.

---

## Power Automate

Leave `POWER_AUTOMATE_PROCEED_URL` and `POWER_AUTOMATE_REJECT_URL` blank in `.env` to run in **mock mode** — the submission endpoint logs payloads instead of posting to PA.

---

## Azure Deployment

### Backend → Azure App Service
1. Create Python 3.11 App Service (Linux)
2. Set startup command to `bash startup.sh` (in Configuration → General Settings)
3. Set `DATABASE_URL` to a persistent path (e.g. `/home/data/pkd.db`)
4. Deploy backend folder via GitHub Actions or `az webapp deploy`

### Frontend → Azure Static Web Apps
1. Create Azure Static Web App linked to your repo
2. Set `VITE_API_BASE_URL` to your App Service URL (e.g. `https://pkd-backend.azurewebsites.net`)
3. Build command: `npm run build`, output: `dist`

---

## Architecture

```
Upload (PDF/DOCX/XLSX/JPG/PNG)
    ↓
/upload → dispatcher → extractor → Canonical JSON
    ↓
/validate → Rule Engine (8 rules) + ML Scorer → Score (0–100)
    ↓
/submit → HMAC-signed webhook → Power Automate proceed/reject flow

Training Studio:
/training/upload → BackgroundTasks → extract → feature build → corpus save → retrain
```
