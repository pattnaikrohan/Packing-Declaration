"""
Layer A — Deterministic Rule Engine
Each rule is a separate function returning a RuleOutcome.
Any ERROR result caps the final score at 70.
"""
from app.ingestion.schema import PackingDeclaration
from app.validation.schemas import RuleOutcome


def _pass(rule_id: str, message: str = "OK") -> RuleOutcome:
    return RuleOutcome(rule_id=rule_id, severity="PASS", message=message)


def _warn(rule_id: str, message: str, fix: str | None = None) -> RuleOutcome:
    return RuleOutcome(rule_id=rule_id, severity="WARNING", message=message, fix=fix)


def _error(rule_id: str, message: str, fix: str) -> RuleOutcome:
    return RuleOutcome(rule_id=rule_id, severity="ERROR", message=message, fix=fix)


# ── RULE-3.1: Letterhead ──────────────────────────────────────────────────────
def rule_3_1(doc: PackingDeclaration) -> RuleOutcome:
    if not doc.letterhead_present:
        return _error(
            "RULE-3.1",
            "Company letterhead not detected.",
            "Re-issue PKD on company letterhead showing full physical address. PO Box alone is not accepted.",
        )
    if not doc.issuer_address:
        return _error(
            "RULE-3.1",
            "Issuer address is missing.",
            "Re-issue PKD on company letterhead showing full physical address. PO Box alone is not accepted.",
        )
    if doc.issuer_address_is_po_box:
        return _error(
            "RULE-3.1",
            "Issuer address is a PO Box — physical address required.",
            "Re-issue PKD on company letterhead showing full physical address. PO Box alone is not accepted.",
        )
    return _pass("RULE-3.1", "Letterhead and physical address present.")


# ── RULE-3.2: Consignment Link ───────────────────────────────────────────────
def rule_3_2(doc: PackingDeclaration) -> RuleOutcome:
    dtype = doc.declaration_type or ""
    is_single = "_SINGLE" in dtype
    is_annual = "_ANNUAL" in dtype

    if is_single and not doc.consignment_ref:
        return _error(
            "RULE-3.2",
            "Single PKD missing consignment link (container, BL, invoice, packing list, or lot).",
            "Add container number, BL, commercial invoice, packing list number, or lot code.",
        )
    if is_annual:
        missing = []
        if not doc.exporter:
            missing.append("exporter")
        if not doc.importer:
            missing.append("importer")
        if missing:
            return _error(
                "RULE-3.2",
                f"Annual PKD missing: {', '.join(missing)}.",
                "Annual PKDs must include both exporter and importer name.",
            )
    return _pass("RULE-3.2", "Consignment link / exporter-importer present.")


# ── RULE-3.3: Q1 ─────────────────────────────────────────────────────────────
def rule_3_3(doc: PackingDeclaration) -> RuleOutcome:
    if doc.q1_unacceptable_material == "BLANK":
        return _error(
            "RULE-3.3",
            "Q1 (unacceptable material) is unanswered.",
            "Q1 must be answered YES or NO.",
        )
    return _pass("RULE-3.3", f"Q1 answered: {doc.q1_unacceptable_material}.")


# ── RULE-3.4: Q2/Q3 Logic ────────────────────────────────────────────────────
def rule_3_4(doc: PackingDeclaration) -> RuleOutcome:
    q2 = doc.q2_timber_bamboo
    q3 = doc.q3_treatment

    if q2 == "NO" and q3 not in ("BLANK", "NOT_APPLICABLE"):
        return _error(
            "RULE-3.4",
            "Q2 is NO but Q3 is answered — conflicting responses.",
            "Q2 is NO but Q3 is answered — conflicting. Remove Q3 or correct Q2.",
        )
    if q2 in ("YES_TIMBER", "YES_BAMBOO") and q3 == "BLANK":
        return _error(
            "RULE-3.4",
            "Q2 declares timber/bamboo used but Q3 treatment is unanswered.",
            "Q2 declares timber/bamboo used — Q3 treatment declaration is mandatory.",
        )
    return _pass("RULE-3.4", "Q2/Q3 logic consistent.")


# ── RULE-3.5: Cleanliness ─────────────────────────────────────────────────────
def rule_3_5(doc: PackingDeclaration) -> RuleOutcome:
    dtype = doc.declaration_type or ""
    q4 = doc.q4_cleanliness

    is_fcl_fcx = dtype in ("FCL_ANNUAL", "FCL_SINGLE", "FCX_SINGLE")
    is_lcl = dtype == "LCL_SINGLE"

    if is_fcl_fcx and q4 == "ABSENT":
        return _error(
            "RULE-3.5",
            "FCL/FCX declaration is missing a cleanliness statement (Q4).",
            "Cleanliness statement mandatory for FCL/FCX.",
        )
    if is_lcl and q4 == "PRESENT":
        return _error(
            "RULE-3.5",
            "LCL declaration must NOT include a cleanliness statement (Q4).",
            "LCL must NOT include cleanliness statement.",
        )
    return _pass("RULE-3.5", "Cleanliness statement appropriate for declaration type.")


# ── RULE-3.6: Endorsement ────────────────────────────────────────────────────
def rule_3_6(doc: PackingDeclaration) -> RuleOutcome:
    if not doc.signed:
        return _error(
            "RULE-3.6",
            "No signature detected.",
            "Signature required.",
        )
    if not doc.printed_name:
        return _error(
            "RULE-3.6",
            "Printed name is missing alongside signature.",
            "Printed name required alongside signature.",
        )
    if doc.signature_type == "stamp_only" and not doc.printed_name:
        return _error(
            "RULE-3.6",
            "Stamp-only signature must identify an individual by name.",
            "Stamp must identify individual.",
        )
    return _pass("RULE-3.6", "Signature and printed name present.")


# ── RULE-3.7: Date ────────────────────────────────────────────────────────────
def rule_3_7(doc: PackingDeclaration) -> RuleOutcome:
    dtype = doc.declaration_type or ""
    is_annual = "_ANNUAL" in dtype
    is_single = "_SINGLE" in dtype

    if is_annual and (not doc.date_issued or not doc.date_valid):
        return _error(
            "RULE-3.7",
            "Annual PKD missing a valid date of issue.",
            "Annual PKDs must show date of issue.",
        )
    if is_single and not doc.date_issued and not doc.voyage_number:
        return _error(
            "RULE-3.7",
            "Single PKD must have either a date or a voyage number.",
            "Date or voyage number required.",
        )
    return _pass("RULE-3.7", "Date/voyage number requirement met.")


# ── RULE-3.8: Alterations ────────────────────────────────────────────────────
def rule_3_8(doc: PackingDeclaration) -> RuleOutcome:
    if doc.alterations_present and not doc.alterations_endorsed:
        return _error(
            "RULE-3.8",
            "Alterations detected but not endorsed.",
            "Alterations must be endorsed.",
        )
    return _pass("RULE-3.8", "No unendorsed alterations.")


# ── Run all rules ─────────────────────────────────────────────────────────────
def run(doc: PackingDeclaration) -> list[RuleOutcome]:
    return [
        rule_3_1(doc),
        rule_3_2(doc),
        rule_3_3(doc),
        rule_3_4(doc),
        rule_3_5(doc),
        rule_3_6(doc),
        rule_3_7(doc),
        rule_3_8(doc),
    ]
