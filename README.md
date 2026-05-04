# PKD Validator

Biosecurity packing declaration validation system for the Australian Department of Agriculture, Fisheries and Forestry (DAFF).

---

## Quick Start (Local)

### 1. Backend

```bash
cd backend

# Copy env file
copy .env.example .env    # Windows
cp .env.example .env      # Linux/Mac

# Create virtual environment and install dependencies
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

pip install -r requirements.txt

# Start server (DB and model_store directories auto-created)
uvicorn app.main:app --reload --port 8000
```

Backend: https://pkd-declaration.azurewebsites.net  
API docs: https://pkd-declaration.azurewebsites.net/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

---

## Docker (Local)

```bash
# Build and run both services
docker compose up --build

# Backend:  https://pkd-declaration.azurewebsites.net
# Frontend: https://delightful-ocean-0ea4d0b00.7.azurestaticapps.net
```

---

## Database

**SQLite** — zero configuration. The database file is auto-created at `backend/data/pkd.db` on first startup.  
In Docker/Azure, it persists at `/home/data/pkd.db`.

---

## OCR

OCR extraction for scanned PDFs and images requires:

**Tesseract**
- Windows: https://github.com/UB-Mannheim/tesseract/wiki  
  - Install and add to PATH, or set `TESSERACT_CMD` in `.env`
- Docker/Azure: **Automatically installed** in the Docker image

**Poppler** (for PDF → image conversion)
- Windows: https://github.com/oschwartz10612/poppler-windows/releases  
  - Extract and add the `bin/` folder to PATH
- Docker/Azure: **Automatically installed** in the Docker image

> **Note:** OCR gracefully degrades if not installed. Digital PDF, DOCX, and XLSX files work without OCR.

---

## Azure Deployment

### Architecture

```
GitHub (main branch)
   ├── backend/**  → GitHub Actions → Docker Build → AAWAI ACR → Azure App Service (Container)
   └── frontend/** → GitHub Actions → npm build    → Azure Static Web Apps
```

### Prerequisites

1. **Azure Container Registry** (`AAWAI.azurecr.io`)
2. **Azure App Service** (Linux, Container) for backend
3. **Azure Static Web App** for frontend
4. **Azure Blob Storage** (`aawaidata` / container: `packing-declaration`)

### Backend → Azure App Service (Docker Container)

The backend Dockerfile bakes in **Tesseract OCR** and **Poppler**, so everything works out of the box.

1. Create a Linux App Service (Container mode)
2. Set the container source to `AAWAI.azurecr.io/pkd-backend:latest`
3. Configure these **App Settings** in the Azure Portal:

| Setting | Value |
|---------|-------|
| `WEBSITES_PORT` | `8000` |
| `DATABASE_URL` | `sqlite:////home/data/pkd.db` |
| `TESSERACT_CMD` | `/usr/bin/tesseract` |
| `AZURE_STORAGE_CONNECTION_STRING` | Your connection string |
| `AZURE_CONTAINER_NAME` | `packing-declaration` |
| `ALLOWED_ORIGINS` | Your Static Web App URL |
| `POWER_AUTOMATE_URL` | Your PA webhook URL |

4. Enable **persistent storage** (mount `/home/data` in App Service → Path Mappings)

### Frontend → Azure Static Web Apps

1. Create an Azure Static Web App linked to this repo
2. In GitHub Secrets, set:
   - `AZURE_STATIC_WEB_APPS_API_TOKEN` — from the Static Web App resource
   - `VITE_API_BASE_URL` — your backend App Service URL (e.g., `https://pkd-backend.azurewebsites.net`)
3. The workflow auto-builds and deploys on push to `main`

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service Principal JSON for `az login` |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | From Azure Static Web App resource |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection string |
| `AZURE_CONTAINER_NAME` | `packing-declaration` |
| `VITE_API_BASE_URL` | Backend URL (e.g., `https://pkd-backend.azurewebsites.net`) |
| `POWER_AUTOMATE_URL` | Power Automate webhook URL |
| `ALLOWED_ORIGINS` | Frontend URL for CORS |

### Setting Up Azure Credentials (Service Principal)

```bash
az ad sp create-for-rbac \
  --name "pkd-github-actions" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/AAWAI \
  --sdk-auth
```

Copy the JSON output and add it as `AZURE_CREDENTIALS` in GitHub → Settings → Secrets.

---

## Power Automate

Leave `POWER_AUTOMATE_URL` blank in `.env` to run in **mock mode** — the submission endpoint logs payloads instead of posting to PA.

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
