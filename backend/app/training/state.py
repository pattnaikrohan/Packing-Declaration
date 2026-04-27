"""
In-memory training job state tracker.
Thread-safe via dict operations (CPython GIL provides sufficient safety for simple reads/writes).
"""
import threading
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TrainingJob(BaseModel):
    job_id: str
    status: str  # queued | extracting | labelling | training | evaluating | done | failed
    label: str   # accepted | rejected
    total_files: int
    processed_files: int = 0
    failed_files: list[str] = []
    records_added: int = 0
    model_swapped: bool = False
    new_f1: Optional[float] = None
    old_f1: Optional[float] = None
    started_at: datetime = datetime.utcnow()
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}


# Global registry
training_jobs: dict[str, TrainingJob] = {}

# Lock to prevent concurrent model writes
retrain_lock = threading.Lock()


def create_job(job_id: str, label: str, total_files: int) -> TrainingJob:
    job = TrainingJob(
        job_id=job_id,
        status="queued",
        label=label,
        total_files=total_files,
    )
    training_jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[TrainingJob]:
    return training_jobs.get(job_id)


def list_jobs(limit: int = 20) -> list[TrainingJob]:
    sorted_jobs = sorted(
        training_jobs.values(),
        key=lambda j: j.started_at,
        reverse=True,
    )
    return sorted_jobs[:limit]
