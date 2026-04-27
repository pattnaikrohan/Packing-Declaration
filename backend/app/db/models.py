import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class DeclarationRecord(Base):
    __tablename__ = "declaration_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    declaration_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    canonical_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feature_vector: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON-encoded float list
    rule_outcomes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    python_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ml_bonus: Mapped[float | None] = mapped_column(Float, nullable=True)

    extraction_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)   # accepted | rejected | null
    outcome_set_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    source: Mapped[str] = mapped_column(String(30), default="validation_flow")
    submitted_to_pa: Mapped[bool] = mapped_column(Boolean, default=False)
    pa_response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
