import os
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db import corpus
from app.ingestion.schema import PackingDeclaration
from app.validation import rule_engine, ml_scorer, feature_builder
from app.validation.score_composer import compose
from app.validation.schemas import ValidationResult, RuleOutcome
from app.config import settings

router = APIRouter(tags=["validation"])
logger = logging.getLogger(__name__)


@router.post("/validate", response_model=ValidationResult)
async def validate(doc: PackingDeclaration, db: AsyncSession = Depends(get_db)):
    """Run two-layer validation on extracted canonical JSON. Saves record to DB."""

    # Layer A
    rule_outcomes = rule_engine.run(doc)

    # Feature vector
    features = feature_builder.build(doc, rule_outcomes)

    # Corpus size for ML gate
    stats = await corpus.get_corpus_stats(db)
    verified_count = stats["accepted_count"] + stats["rejected_count"]

    # Layer B
    ml_bonus, ml_active = ml_scorer.score(features, verified_count)

    # Compose final score
    composition = compose(rule_outcomes, ml_bonus)

    # Save to DB
    record = await corpus.save_record(
        db,
        canonical_json=doc.model_dump(),
        feature_vector=features,
        rule_outcomes={r.rule_id: r.model_dump() for r in rule_outcomes},
        python_score=composition["final_score"],
        ml_bonus=ml_bonus,
        extraction_method=doc.extraction_method,
        ocr_confidence=doc.ocr_confidence,
        source="validation_flow",
    )

    return ValidationResult(
        record_id=record.id,
        declaration_type=doc.declaration_type,
        rule_outcomes=rule_outcomes,
        rule_score=composition["rule_score"],
        ml_bonus=ml_bonus,
        ml_active=ml_active,
        final_score=composition["final_score"],
        passed=composition["passed"],
        error_count=composition["error_count"],
        warning_count=composition["warning_count"],
    )


@router.get("/models/status")
async def models_status(db: AsyncSession = Depends(get_db)):
    stats = await corpus.get_corpus_stats(db)
    verified = stats["accepted_count"] + stats["rejected_count"]
    ml_active = verified >= settings.MIN_TRAINING_RECORDS and ml_scorer._models_loaded

    # Read model metadata if available
    meta_path = os.path.join(settings.MODEL_STORE_PATH, "model_meta.json")
    model_meta = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            model_meta = json.load(f)

    return {
        "ml_active": ml_active,
        "verified_record_count": verified,
        "min_required": settings.MIN_TRAINING_RECORDS,
        "last_retrain": model_meta.get("trained_at"),
        "current_f1": model_meta.get("f1_score"),
        "model_version": model_meta.get("version"),
    }


@router.patch("/corpus/{record_id}/outcome")
async def set_outcome(
    record_id: str,
    outcome: str,
    db: AsyncSession = Depends(get_db),
):
    """Label a validated record as accepted or rejected."""
    if outcome not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="outcome must be 'accepted' or 'rejected'")

    record = await corpus.set_outcome(db, record_id, outcome)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return {"record_id": record_id, "outcome": outcome, "updated_at": record.outcome_set_at}
