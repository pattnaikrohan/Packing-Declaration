"""
Feature vector builder — produces the 36-element float list used by both ML models.
"""
from datetime import date
from typing import Optional

from app.ingestion.schema import PackingDeclaration
from app.validation.schemas import RuleOutcome

RULE_ORDER = [
    "RULE-3.1", "RULE-3.2", "RULE-3.3", "RULE-3.4",
    "RULE-3.5", "RULE-3.6", "RULE-3.7", "RULE-3.8",
]


def _q1_code(v: str) -> int:
    return {"YES": 1, "NO": 0, "BLANK": -1}.get(v, -1)


def _q2_code(v: str) -> int:
    return {"YES_TIMBER": 2, "YES_BAMBOO": 1, "NO": 0, "BLANK": -1}.get(v, -1)


def _q3_code(v: str) -> int:
    return {"ISPM15": 3, "DAFF_CERTIFIED": 2, "NOT_TREATED": 1, "NOT_APPLICABLE": 0, "BLANK": -1}.get(v, -1)


def _q4_code(v: str) -> int:
    return 1 if v == "PRESENT" else 0


def _days_since_issue(date_str: Optional[str]) -> float:
    if not date_str:
        return 0.0
    try:
        d = date.fromisoformat(date_str)
        delta = (date.today() - d).days
        return float(delta)
    except Exception:
        return 0.0


def build(doc: PackingDeclaration, rule_outcomes: list[RuleOutcome]) -> list[float]:
    m = doc

    rule_error_map = {r.rule_id: (1 if r.severity == "ERROR" else 0) for r in rule_outcomes}

    total_errors = sum(1 for r in rule_outcomes if r.severity == "ERROR")
    total_warnings = sum(1 for r in rule_outcomes if r.severity == "WARNING")

    dtype = doc.declaration_type or ""

    features = [
        # Metadata presence/quality (12 features)
        float(m.letterhead_present),
        float(m.issuer_address is not None),
        float(not m.issuer_address_is_po_box),
        float(m.consignment_ref is not None),
        float(m.exporter is not None),
        float(m.importer is not None),
        float(m.vessel_name is not None),
        float(m.voyage_number is not None),
        float(m.date_issued is not None),
        float(m.date_valid),
        float(m.signed),
        float(m.printed_name is not None),
        # Declaration type one-hot (4 features)
        float(dtype == "FCL_ANNUAL"),
        float(dtype == "FCL_SINGLE"),
        float(dtype == "LCL_SINGLE"),
        float(dtype == "FCX_SINGLE"),
        # Question answers coded (4 features)
        float(_q1_code(doc.q1_unacceptable_material)),
        float(_q2_code(doc.q2_timber_bamboo)),
        float(_q3_code(doc.q3_treatment)),
        float(_q4_code(doc.q4_cleanliness)),
        # Per-rule error flags (8 features)
        float(rule_error_map.get("RULE-3.1", 0)),
        float(rule_error_map.get("RULE-3.2", 0)),
        float(rule_error_map.get("RULE-3.3", 0)),
        float(rule_error_map.get("RULE-3.4", 0)),
        float(rule_error_map.get("RULE-3.5", 0)),
        float(rule_error_map.get("RULE-3.6", 0)),
        float(rule_error_map.get("RULE-3.7", 0)),
        float(rule_error_map.get("RULE-3.8", 0)),
        # Derived numeric features (8 features)
        min(1.0, len(m.issuer_address or "") / 200.0),
        min(1.0, len(m.consignment_ref or "") / 50.0),
        float(doc.ocr_confidence),
        min(10.0, _days_since_issue(m.date_issued) / 365.0),   # years since issue, capped at 10
        float(total_errors),
        float(total_warnings),
        float(doc.alterations_present),
        float(doc.alterations_endorsed),
    ]

    assert len(features) == 36, f"Feature vector length mismatch: {len(features)}"
    return features
