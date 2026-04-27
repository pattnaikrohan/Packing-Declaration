from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from app.ingestion import dispatcher, ml_engine, ocr_extractor, job_manager
from app.ingestion.schema import PackingDeclaration, TripleExtraction
from app.azure_storage import upload_to_blob_storage
import json
import logging
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["ingestion"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

@router.post("/clear-storage")
async def clear_storage(background_tasks: BackgroundTasks):
    """
    Clears all existing files in the Azure Blob Storage folder before a new batch.
    """
    from app.azure_storage import clear_blob_storage
    background_tasks.add_task(clear_blob_storage)
    return {"status": "clearing"}

@router.post("", response_model=TripleExtraction)
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Accept a packing declaration file and return a TripleExtraction object 
    containing OCR, ML, and PA results for comparison.
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")

    try:
        # Upload to Azure Blob Storage FIRST (synchronous) so Power Automate
        # can find the file when AI Builder processes it
        await upload_to_blob_storage(file_bytes, file.filename)

        # returns TripleExtraction (OCR + ML + PA from Power Automate)
        result = dispatcher.extract(file_bytes, file.filename, file.content_type)
        return result
    except Exception as e:
        logger.error(f"Triple Extraction failed: {e}")
        raise HTTPException(status_code=422, detail=f"Extraction failed: {str(e)}")

@router.post("/label")
async def label_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    labels_json: str = File(...)
):
    """
    Accept a training file and its manual labels.
    """
    file_bytes = await file.read()
    
    # Schedule the Azure Blob Storage upload in the background
    background_tasks.add_task(upload_to_blob_storage, file_bytes, file.filename)
    
    try:
        labels = json.loads(labels_json)
        count = ml_engine.add_labelled_sample(file_bytes, file.filename, file.content_type, labels)
        return {"status": "success", "corpus_size": count}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Labelling failed: {str(e)}")

@router.post("/roi-extract")
async def extract_region_of_interest(
    file: UploadFile = File(...),
    x1: float = Form(...),
    y1: float = Form(...),
    x2: float = Form(...),
    y2: float = Form(...)
):
    """
    Extract text from a specific region of a document.
    """
    file_bytes = await file.read()
    is_pdf = file.content_type == "application/pdf" or file.filename.lower().endswith(".pdf")
    try:
        text = ocr_extractor.extract_roi(file_bytes, x1, y1, x2, y2, is_pdf)
        return {"text": text}
    except Exception as e:
        logger.error(f"ROI extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"ROI Scan Fault: {str(e)}")

@router.post("/bulk")
async def bulk_upload_training(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    label_type: str = Form(...)
):
    """
    Accept a batch of files and start a background training job.
    """
    job_id = job_manager.HUB.create_job(label=label_type, total_files=len(files))
    
    # Define a background task function (inline for simplicity or move to util)
    async def process_bulk():
        job_manager.HUB.update_job(job_id, status="processing")
        
        # Binary label matrix
        if label_type == "accepted":
            labels = {
                "declaration_type": "FCL_ANNUAL", "q1_unacceptable_material": "NO",
                "q2_timber_bamboo": "NO", "q3_treatment": "ISPM15",
                "q4_cleanliness": "PRESENT", "signed": "SIGNED"
            }
        else:
            labels = {
                "declaration_type": "FCL_ANNUAL", "q1_unacceptable_material": "YES",
                "q2_timber_bamboo": "YES_TIMBER", "q3_treatment": "NOT_TREATED",
                "q4_cleanliness": "ABSENT", "signed": "UNSIGNED"
            }

        processed = 0
        added = 0
        failed = []

        for file in files:
            try:
                # Read bytes synchronously here since we are in background
                file_bytes = await file.read()
                
                # Upload to Azure
                await upload_to_blob_storage(file_bytes, file.filename)
                
                ml_engine.add_labelled_sample(file_bytes, file.filename, file.content_type, labels)
                added += 1
            except Exception as e:
                failed.append(f"{file.filename}: {str(e)}")
            finally:
                processed += 1
                job_manager.HUB.update_job(job_id, processed_files=processed, records_added=added, failed_files=failed)

        job_manager.HUB.update_job(job_id, status="done")

    background_tasks.add_task(process_bulk)
    return {"job_id": job_id, "status": "queued"}


@router.post("/train")
async def train_model(background_tasks: BackgroundTasks):
    """
    Retrain the neural model in the background and track F1 scores.
    """
    job_id = job_manager.HUB.create_job(label="force_retrain", total_files=1)
    
    async def run_training():
        job_manager.HUB.update_job(job_id, status="processing", old_f1=ml_engine.engine.accuracy_score)
        
        corpus_path = Path("app/data/training_corpus.json")
        if not corpus_path.exists():
            job_manager.HUB.update_job(job_id, status="failed", error="No training data found.")
            return

        try:
            with open(corpus_path, "r") as f:
                data = json.load(f)
            
            result = ml_engine.engine.train(data)
            if result.get("status") == "success":
                job_manager.HUB.update_job(
                    job_id, 
                    status="done", 
                    new_f1=result["accuracy_estimate"],
                    model_swapped=True
                )
            else:
                job_manager.HUB.update_job(job_id, status="failed", error=result.get("message"))
        except Exception as e:
            job_manager.HUB.update_job(job_id, status="failed", error=str(e))

    background_tasks.add_task(run_training)
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs")
async def list_jobs():
    """
    Get the list of all background training jobs for the Monitor.
    """
    return job_manager.HUB.list_jobs()


@router.get("/ml-stats")
async def get_ml_stats():
    """
    Get current intelligence metrics for the Neural Studio.
    """
    corpus_path = Path("app/data/training_corpus.json")
    sample_count = 0
    if corpus_path.exists():
        with open(corpus_path, "r") as f:
            sample_count = len(json.load(f))
            
    return {
        "is_trained": ml_engine.engine.is_trained,
        "sample_count": sample_count,
        "accuracy_estimate": ml_engine.engine.accuracy_score if ml_engine.engine.is_trained else 0.0,
        "model_type": "RandomForest Multi-Output Ensemble",
        "last_trained": "Active" if ml_engine.engine.is_trained else "Cold Start"
    }
