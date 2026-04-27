import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class TrainingJob(BaseModel):
    job_id: str
    status: str = "queued"  # queued, processing, done, failed
    label: str
    total_files: int = 0
    processed_files: int = 0
    records_added: int = 0
    failed_files: List[str] = []
    started_at: str
    finished_at: Optional[str] = None
    old_f1: Optional[float] = None
    new_f1: Optional[float] = None
    model_swapped: bool = False
    error: Optional[str] = None

class ComplianceBatchJob(BaseModel):
    job_id: str
    status: str = "queued"
    total_files: int = 0
    processed_files: int = 0
    results: List[Any] = []  # List of PackingDeclaration
    mismatches: List[str] = []
    started_at: str
    finished_at: Optional[str] = None

class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Any] = {}

    def create_job(self, label: str, total_files: int = 0) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = TrainingJob(
            job_id=job_id,
            label=label,
            total_files=total_files,
            started_at=datetime.datetime.now().isoformat()
        )
        self.jobs[job_id] = job
        return job_id

    def create_batch_job(self, total_files: int = 0) -> str:
        job_id = "batch_" + str(uuid.uuid4())[:6]
        job = ComplianceBatchJob(
            job_id=job_id,
            total_files=total_files,
            started_at=datetime.datetime.now().isoformat()
        )
        self.jobs[job_id] = job
        return job_id

    def update_job(self, job_id: str, **kwargs):
        if job_id in self.jobs:
            job = self.jobs[job_id]
            for k, v in kwargs.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            
            if "status" in kwargs and kwargs["status"] in ["done", "failed"]:
                job.finished_at = datetime.datetime.now().isoformat()

    def get_job(self, job_id: str) -> Optional[Any]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[Any]:
        return sorted(self.jobs.values(), key=lambda x: x.started_at, reverse=True)

    @staticmethod
    def classify_document(text: str) -> str:
        """Heuristic classification for batch matching."""
        upper = text.upper()[:1200]
        if "PACKING DECLARATION" in upper or "PKD" in upper:
            return "PKD"
        if "BILL OF LADING" in upper or " WAYBILL" in upper:
            return "BL"
        if "INVOICE" in upper:
            return "INVOICE"
        if "PACKING LIST" in upper:
            return "PACKING_LIST"
        return "UNKNOWN"

    @staticmethod
    def run_cross_document_checks(pkd: Any, batch_results: List[Any]) -> List[str]:
        """
        Compare the PKD against other documents in the same shipment.
        Logic: Match by Vessel/Voyage OR Consignment Ref.
        """
        issues = []
        if not pkd.consignment_ref and not pkd.vessel_name:
            return issues

        for other in batch_results:
            if other.file_name == pkd.file_name:
                continue
            
            # 1. Check for Vessel Mismatch
            if pkd.vessel_name and other.vessel_name:
                if pkd.vessel_name.strip().upper() != other.vessel_name.strip().upper():
                    issues.append(f"Vessel Mismatch: PKD says '{pkd.vessel_name}' but {other.file_name} says '{other.vessel_name}'")
            
            # 2. Check for Consignment ID Mismatch (Critical)
            if pkd.consignment_ref and other.consignment_ref:
                if pkd.consignment_ref.strip().upper() != other.consignment_ref.strip().upper():
                    issues.append(f"Consignment ID Mismatch: PKD says '{pkd.consignment_ref}' but {other.file_name} says '{other.consignment_ref}'")
        
        return issues

# Singleton
HUB = JobManager()
