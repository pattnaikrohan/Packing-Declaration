"""
Background training processor — runs in FastAPI BackgroundTasks thread.
Never blocks the API. Individual file failures are caught and logged.
A threading.Lock wraps the model write step to prevent concurrent joblib writes.
"""
import logging
import uuid
from datetime import datetime

from app.training.state import training_jobs, retrain_lock
from app.ingestion import dispatcher

logger = logging.getLogger(__name__)


async def process_training_batch(job_id: str, files_data: list[dict], label: str):
    """
    files_data: list of {"filename": str, "content_type": str, "bytes": bytes}
    label: "accepted" | "rejected"
    """
    from app.db.database import AsyncSessionLocal
    from app.db import corpus
    from app.validation import rule_engine, feature_builder

    job = training_jobs[job_id]
    job.status = "extracting"

    async with AsyncSessionLocal() as db:
        for file_info in files_data:
            filename = file_info["filename"]
            try:
                # Step 1: Extract
                canonical = dispatcher.extract(
                    file_info["bytes"],
                    filename,
                    file_info["content_type"],
                )

                # Step 2: Rule engine
                rule_outcomes = rule_engine.run(canonical)

                # Step 3: Feature vector
                features = feature_builder.build(canonical, rule_outcomes)

                # Step 4: Save to corpus with label
                await corpus.save_record(
                    db,
                    canonical_json=canonical.model_dump(),
                    feature_vector=features,
                    rule_outcomes={r.rule_id: r.model_dump() for r in rule_outcomes},
                    extraction_method=canonical.extraction_method,
                    ocr_confidence=canonical.ocr_confidence,
                    outcome=label,
                    source="training_upload",
                )

                job.records_added += 1

            except Exception as e:
                logger.warning(f"[training] Failed to process {filename}: {e}")
                job.failed_files.append(filename)

            finally:
                job.processed_files += 1

    # Step 5: Attempt model retrain (with lock to prevent concurrent writes)
    job.status = "training"
    try:
        with retrain_lock:
            from app.training import train_models
            result = train_models.retrain_if_ready()

        job.model_swapped = result.swapped
        job.new_f1 = result.new_f1
        job.old_f1 = result.old_f1
        job.status = "done"
    except Exception as e:
        logger.error(f"[training] Retrain failed for job {job_id}: {e}")
        job.status = "failed"
        job.error = str(e)

    job.finished_at = datetime.utcnow()
    logger.info(
        f"[training] Job {job_id} finished — "
        f"{job.records_added} records added, swapped={job.model_swapped}"
    )
