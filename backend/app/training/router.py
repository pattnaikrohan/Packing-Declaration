import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db import corpus
from app.training import state as job_state
from app.training.background_trainer import process_training_batch
from app.training.state import training_jobs
from app.config import settings

router = APIRouter(prefix="/training", tags=["training"])
logger = logging.getLogger(__name__)


# ── POST /training/upload ─────────────────────────────────────────────────────
@router.post("/upload")
async def training_upload(
    background_tasks: BackgroundTasks,
    label: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """
    Non-blocking. Reads file bytes immediately (before background task runs),
    creates job, queues background processing, returns job_id instantly.
    """
    if label not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="label must be 'accepted' or 'rejected'")
    if not files:
        raise HTTPException(status_code=400, detail="At least one file required")

    # Read all file bytes BEFORE handing off (UploadFile objects are not safe to pass across threads)
    files_data = []
    for f in files:
        content = await f.read()
        files_data.append({
            "filename": f.filename or "upload",
            "content_type": f.content_type or "",
            "bytes": content,
        })

    job_id = str(uuid.uuid4())
    job_state.create_job(job_id, label, len(files_data))

    background_tasks.add_task(process_training_batch, job_id, files_data, label)

    logger.info(f"[training] Job {job_id} queued — {len(files_data)} files, label={label}")

    return {
        "job_id": job_id,
        "status": "queued",
        "total_files": len(files_data),
        "label": label,
    }


# ── GET /training/jobs/{job_id} ───────────────────────────────────────────────
@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_state.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


# ── GET /training/jobs ────────────────────────────────────────────────────────
@router.get("/jobs")
async def list_jobs():
    return [j.model_dump() for j in job_state.list_jobs(limit=20)]


# ── GET /training/corpus/stats ────────────────────────────────────────────────
@router.get("/corpus/stats")
async def corpus_stats(db: AsyncSession = Depends(get_db)):
    stats = await corpus.get_corpus_stats(db)
    verified = stats["accepted_count"] + stats["rejected_count"]
    ml_active = verified >= settings.MIN_TRAINING_RECORDS

    return {
        **stats,
        "ml_active": ml_active,
        "min_required": settings.MIN_TRAINING_RECORDS,
    }


# ── DELETE /training/corpus/{record_id} ──────────────────────────────────────
@router.delete("/corpus/{record_id}")
async def delete_corpus_record(record_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await corpus.delete_record(db, record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    stats = await corpus.get_corpus_stats(db)
    return {"deleted": True, "record_id": record_id, **stats}


# ── POST /training/retrain/force ──────────────────────────────────────────────
@router.post("/retrain/force")
async def force_retrain(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Force an immediate retrain. Returns instantly — training runs in background."""
    stats = await corpus.get_corpus_stats(db)
    verified = stats["accepted_count"] + stats["rejected_count"]

    if verified < settings.MIN_TRAINING_RECORDS:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {settings.MIN_TRAINING_RECORDS} verified records. Have {verified}.",
        )

    # Check if any job is already running
    active = [j for j in training_jobs.values() if j.status not in ("done", "failed")]
    if active:
        raise HTTPException(status_code=409, detail="A training job is already running.")

    job_id = str(uuid.uuid4())
    job_state.create_job(job_id, "force_retrain", 0)

    def _force():
        job = training_jobs[job_id]
        job.status = "training"
        try:
            from app.training.state import retrain_lock
            from app.training import train_models
            with retrain_lock:
                result = train_models.retrain_if_ready()
            job.model_swapped = result.swapped
            job.new_f1 = result.new_f1
            job.old_f1 = result.old_f1
            job.status = "done"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        finally:
            from datetime import datetime
            job.finished_at = datetime.utcnow()

    background_tasks.add_task(_force)

    return {"job_id": job_id, "status": "queued", "message": "Force retrain started in background."}
