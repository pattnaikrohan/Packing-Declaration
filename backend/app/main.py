from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ingestion.router import router as ingestion_router
from app.submission.router import router as submission_router


app = FastAPI(
    title="PKD Converter",
    description="Packing Declaration → JSON → Power Automate",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(submission_router)


@app.get("/health")
async def health():
    return {"status": "ok", "pa_url_configured": bool(settings.POWER_AUTOMATE_URL)}
