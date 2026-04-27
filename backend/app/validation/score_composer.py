"""
Score composer — combines rule outcomes and ML bonus into final 0-100 score.
"""
from app.validation.schemas import RuleOutcome

RULE_WEIGHTS = {
    "RULE-3.1": 15,
    "RULE-3.2": 14,
    "RULE-3.3": 10,
    "RULE-3.4": 15,
    "RULE-3.5": 10,
    "RULE-3.6": 12,
    "RULE-3.7":  8,
    "RULE-3.8":  6,
}

PASS_THRESHOLD = 85


def compose(rule_outcomes: list[RuleOutcome], ml_bonus: float) -> dict:
    """
    Returns dict with: rule_score, final_score, passed, error_count, warning_count
    """
    outcomes_by_id = {r.rule_id: r for r in rule_outcomes}

    rule_score = sum(
        w for rule_id, w in RULE_WEIGHTS.items()
        if outcomes_by_id.get(rule_id) and outcomes_by_id[rule_id].severity != "ERROR"
    )

    has_error = any(r.severity == "ERROR" for r in rule_outcomes)
    if has_error:
        rule_score = min(rule_score, 70)

    final_score = max(0, min(100, int(rule_score + round(ml_bonus))))

    error_count = sum(1 for r in rule_outcomes if r.severity == "ERROR")
    warning_count = sum(1 for r in rule_outcomes if r.severity == "WARNING")

    return {
        "rule_score": rule_score,
        "final_score": final_score,
        "passed": final_score >= PASS_THRESHOLD,
        "error_count": error_count,
        "warning_count": warning_count,
    }
