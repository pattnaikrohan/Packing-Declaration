import json
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeclarationRecord


async def save_record(
    db: AsyncSession,
    *,
    canonical_json: dict,
    feature_vector: list[float] | None = None,
    rule_outcomes: dict | None = None,
    python_score: int | None = None,
    ml_bonus: float | None = None,
    extraction_method: str | None = None,
    ocr_confidence: float | None = None,
    outcome: str | None = None,
    source: str = "validation_flow",
) -> DeclarationRecord:
    record = DeclarationRecord(
        id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        declaration_type=canonical_json.get("declaration_type"),
        canonical_json=canonical_json,
        feature_vector=json.dumps(feature_vector) if feature_vector else None,
        rule_outcomes=rule_outcomes,
        python_score=python_score,
        ml_bonus=ml_bonus,
        extraction_method=extraction_method,
        ocr_confidence=ocr_confidence,
        outcome=outcome,
        outcome_set_at=datetime.utcnow() if outcome else None,
        source=source,
        submitted_to_pa=False,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def set_outcome(db: AsyncSession, record_id: str, outcome: str) -> DeclarationRecord | None:
    result = await db.execute(select(DeclarationRecord).where(DeclarationRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record:
        record.outcome = outcome
        record.outcome_set_at = datetime.utcnow()
        await db.commit()
        await db.refresh(record)
    return record


async def mark_submitted(db: AsyncSession, record_id: str, pa_response_code: int):
    result = await db.execute(select(DeclarationRecord).where(DeclarationRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record:
        record.submitted_to_pa = True
        record.pa_response_code = pa_response_code
        await db.commit()


async def delete_record(db: AsyncSession, record_id: str) -> bool:
    result = await db.execute(
        delete(DeclarationRecord).where(DeclarationRecord.id == record_id)
    )
    await db.commit()
    return result.rowcount > 0


async def get_verified_records(db: AsyncSession) -> list[DeclarationRecord]:
    """Returns all records with an outcome (accepted/rejected) — the ML training corpus."""
    result = await db.execute(
        select(DeclarationRecord).where(
            DeclarationRecord.outcome.in_(["accepted", "rejected"])
        )
    )
    return result.scalars().all()


async def get_corpus_stats(db: AsyncSession) -> dict[str, Any]:
    total = await db.scalar(select(func.count()).select_from(DeclarationRecord))
    accepted = await db.scalar(
        select(func.count()).select_from(DeclarationRecord).where(DeclarationRecord.outcome == "accepted")
    )
    rejected = await db.scalar(
        select(func.count()).select_from(DeclarationRecord).where(DeclarationRecord.outcome == "rejected")
    )
    pending = await db.scalar(
        select(func.count()).select_from(DeclarationRecord).where(DeclarationRecord.outcome.is_(None))
    )

    # Declaration type breakdown (only verified records)
    breakdown_rows = await db.execute(
        select(DeclarationRecord.declaration_type, func.count().label("cnt"))
        .where(DeclarationRecord.outcome.in_(["accepted", "rejected"]))
        .group_by(DeclarationRecord.declaration_type)
    )
    breakdown = {row.declaration_type or "UNKNOWN": row.cnt for row in breakdown_rows}

    return {
        "total_records": total or 0,
        "accepted_count": accepted or 0,
        "rejected_count": rejected or 0,
        "pending_count": pending or 0,
        "declaration_type_breakdown": breakdown,
    }
