"""
DAFF Deterministic Compliance Engine.
Evaluates extracted PackingDeclarations against strict biosecurity rules.
Based on DAFF Packing Declaration Fact Sheet (December 2024).
"""
import logging
from app.ingestion.schema import PackingDeclaration, ComplianceReport, ComplianceIssue

logger = logging.getLogger(__name__)

def evaluate_compliance(pkd: PackingDeclaration) -> ComplianceReport:
    """
    Main entry point for deterministic validation.
    Applies strict rules sequentially.
    """
    report = ComplianceReport()
    errors = []
    warnings = []
    instructions = []

    # ── RULE 3.1: ISSUER & LETTERHEAD ────────────────────────────────────────
    if not pkd.letterhead_present:
        errors.append(ComplianceIssue(
            issue="Letterhead Missing",
            reason="DAFF requires PKDs to be issued on company letterhead or with a company stamp substitute.",
            rule="3.1 Issuer & Letterhead"
        ))
        instructions.append("Re-issue PKD on company letterhead.")

    if not pkd.issuer_company:
        errors.append(ComplianceIssue(
            issue="Issuer Company Name Missing",
            reason="The entity that packed or observed the packing must be identified.",
            rule="3.1 Issuer & Letterhead"
        ))

    if not pkd.issuer_address:
        errors.append(ComplianceIssue(
            issue="Physical Address Missing",
            reason="A physical address is required. A PO Box alone is not acceptable.",
            rule="3.1 Issuer & Letterhead"
        ))
    elif pkd.issuer_address_is_po_box:
        errors.append(ComplianceIssue(
            issue="PO Box Used for Address",
            reason="A PO Box alone is not acceptable for DAFF declarations.",
            rule="3.1 Issuer & Letterhead"
        ))
        instructions.append("Provide a physical address on the declaration (PO Box is not sufficient).")

    # ── RULE 3.2: CONSIGNMENT LINK ───────────────────────────────────────────
    is_annual = pkd.declaration_type in ("FCL_ANNUAL", "LCL_ANNUAL")
    if not is_annual:
        if not pkd.consignment_ref:
            errors.append(ComplianceIssue(
                issue="Consignment Link Missing",
                reason="Single/Consignment-specific PKDs must include a unique link (Container, B/L, or Invoice #).",
                rule="3.2 Consignment Link"
            ))
            instructions.append("Include a unique consignment link (e.g. Container number or B/L number).")

    # ── RULE: ENUM VALIDATION ────────────────────────────────────────────────
    valid_q1 = ["YES", "NO", "BLANK"]
    valid_q2 = ["YES_TIMBER", "YES_BAMBOO", "NO", "BLANK"]
    valid_q3 = ["ISPM15", "DAFF_CERTIFIED", "NOT_TREATED", "NOT_APPLICABLE", "BLANK"]
    valid_q4 = ["PRESENT", "ABSENT", "BLANK"]

    if pkd.q1_unacceptable_material not in valid_q1:
        errors.append(ComplianceIssue(issue="Invalid Q1 Value", reason=f"Extracted value '{pkd.q1_unacceptable_material}' is not a valid DAFF option.", rule="Data Integrity"))
    if pkd.q2_timber_bamboo not in valid_q2:
        errors.append(ComplianceIssue(issue="Invalid Q2 Value", reason=f"Extracted value '{pkd.q2_timber_bamboo}' is not a valid DAFF option.", rule="Data Integrity"))
    if pkd.q3_treatment not in valid_q3:
        errors.append(ComplianceIssue(issue="Invalid Q3 Value", reason=f"Extracted value '{pkd.q3_treatment}' is not a valid DAFF option.", rule="Data Integrity"))
    if pkd.q4_cleanliness not in valid_q4:
        errors.append(ComplianceIssue(issue="Invalid Q4 Value", reason=f"Extracted value '{pkd.q4_cleanliness}' is not a valid DAFF option.", rule="Data Integrity"))

    # ── RULE 3.3: UNACCEPTABLE MATERIAL (Q1) ─────────────────────────────────
    if pkd.q1_unacceptable_material == "BLANK":
        errors.append(ComplianceIssue(
            issue="Q1 Declaration Missing",
            reason="The declaration regarding unacceptable packaging materials is mandatory.",
            rule="3.3 Unacceptable Packaging Material"
        ))
        instructions.append("Ensure Q1 (Unacceptable Material) is clearly answered YES or NO.")

    # ── RULE 3.4: TIMBER / BAMBOO LOGIC (CRITICAL) ───────────────────────────
    if pkd.q2_timber_bamboo == "NO":
        if pkd.q3_treatment != "BLANK" and pkd.q3_treatment != "NOT_APPLICABLE":
            errors.append(ComplianceIssue(
                issue="Conflicting Timber Declaration",
                reason="Q2 is marked 'NO' (nil timber), but Q3 treatment info is provided. This is a contradiction.",
                rule="3.4 Timber / Bamboo Logic"
            ))
            instructions.append("If no timber/bamboo is used (Q2=NO), Q3 treatment details must be removed.")
    elif pkd.q2_timber_bamboo in ("YES_TIMBER", "YES_BAMBOO"):
        if pkd.q3_treatment == "BLANK":
            errors.append(ComplianceIssue(
                issue="Missing Treatment Declaration",
                reason="Q2 is marked 'YES' (timber/bamboo used), but Q3 treatment details are missing.",
                rule="3.4 Timber / Bamboo Logic"
            ))
            instructions.append("Provide treatment details in Q3 (ISPM 15, Treated, or Not Treated) as Q2 is YES.")
    elif pkd.q2_timber_bamboo == "BLANK":
        errors.append(ComplianceIssue(
            issue="Q2 Declaration Missing",
            reason="Timber/bamboo declaration is mandatory.",
            rule="3.4 Timber / Bamboo Logic"
        ))

    # ── RULE 3.5: CLEANLINESS STATEMENT ──────────────────────────────────────
    is_lcl = pkd.declaration_type in ("LCL_SINGLE", "LCL_ANNUAL")
    if is_lcl:
        if pkd.q4_cleanliness != "BLANK":
            errors.append(ComplianceIssue(
                issue="LCL Cleanliness Statement Present",
                reason="Cleanliness statements MUST NOT appear on LCL declarations as they are deconsolidated at depots.",
                rule="3.5 Cleanliness Statement"
            ))
            instructions.append("Remove the cleanliness statement (Q4) for LCL declarations.")
    else:
        # FCL / FCX / Annual FCL
        if pkd.q4_cleanliness == "BLANK" or pkd.q4_cleanliness == "ABSENT":
            errors.append(ComplianceIssue(
                issue="FCL Cleanliness Statement Missing",
                reason="A container cleanliness statement is required for FCL/FCX consignments.",
                rule="3.5 Cleanliness Statement"
            ))
            instructions.append("Provide a cleanliness statement (Q4) for FCL/FCX consignments.")

    # ── RULE 3.6: ENDORSEMENT ────────────────────────────────────────────────
    if not pkd.signed:
        errors.append(ComplianceIssue(
            issue="Missing Signature",
            reason="The declaration must be endorsed with an acceptable signature (Handwritten, DocuSign, or Type).",
            rule="3.6 Endorsement"
        ))
    if not pkd.printed_name:
        errors.append(ComplianceIssue(
            issue="Missing Printed Name",
            reason="Employee's printed name is required following the signature.",
            rule="3.6 Endorsement"
        ))
    
    if (not pkd.signed or not pkd.printed_name):
        instructions.append("Obtain a signed copy with both a signature and the employee's printed name.")

    # ── RULE 3.7: DATE OF ISSUE ──────────────────────────────────────────────
    if not pkd.date_issued:
        # For consignment-specific, vessel/voyage can substitute.
        # But for Annual, it's a hard fail.
        if is_annual:
            errors.append(ComplianceIssue(
                issue="Annual PKD Date Missing",
                reason="Annual Packing Declarations MUST show an issue date to determine validity window.",
                rule="3.7 Date of Issue"
            ))
        else:
            if not pkd.vessel_name or not pkd.voyage_number:
                errors.append(ComplianceIssue(
                    issue="Issue Date Missing",
                    reason="Consignment-specific PKDs must be dated, or provide BOTH Vessel and Voyage as a substitute.",
                    rule="3.7 Date of Issue"
                ))
        if not any(e.issue == "Issue Date Missing" for e in errors):
            # Instructions only if not already blocked by hard missing date logic
            pass
        else:
            instructions.append("Include a date of issue (Day, Month, Year).")

    # ── RULE 3.8: ALTERATIONS ────────────────────────────────────────────────
    if pkd.alterations_present and not pkd.alterations_endorsed:
        errors.append(ComplianceIssue(
            issue="Unendorsed Alterations",
            reason="Any manual changes or strike-outs must be endorsed with a signature and printed name.",
            rule="3.8 Alterations"
        ))
        instructions.append("Ensure any manual corrections are initialed/endorsed by the issuer.")

    # ── RULE: CONFIDENCE SAFEGUARDS ──────────────────────────────────────────
    if pkd.field_scores:
        low_conf_fields = [f for f, s in pkd.field_scores.items() if s < 0.8]
        for field in low_conf_fields:
            warnings.append(ComplianceIssue(
                issue="Low Confidence Extraction",
                reason=f"Field '{field}' was extracted with low confidence score. Manual review recommended.",
                rule="Safety / ML Integrity"
            ))

    # ── FINAL COMPILATION ────────────────────────────────────────────────────
    report.critical_errors = errors
    report.warnings = warnings
    report.fix_instructions = list(dict.fromkeys(instructions)) # unique only
    report.rules_version = "DAFF-2024-V1.0"
    report.model_version = "LAYOUTLM-V1"

    if not errors:
        report.overall_outcome = "Acceptable"
    else:
        report.overall_outcome = "Not acceptable for DAFF assessment"

    return report
