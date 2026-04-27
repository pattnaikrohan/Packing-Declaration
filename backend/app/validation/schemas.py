from pydantic import BaseModel
from typing import Optional, Literal, List


class RuleOutcome(BaseModel):
    rule_id: str
    severity: Literal["PASS", "WARNING", "ERROR"]
    message: str
    fix: Optional[str] = None


class ValidationResult(BaseModel):
    record_id: str
    declaration_type: Optional[str]
    rule_outcomes: List[RuleOutcome]
    rule_score: int
    ml_bonus: float
    ml_active: bool
    final_score: int
    passed: bool
    error_count: int
    warning_count: int
