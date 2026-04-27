from pydantic import BaseModel
from typing import Optional, Literal


class ComplianceIssue(BaseModel):
    issue: str
    reason: str
    rule: str  # Reference to Fact Sheet or Policy

class ComplianceReport(BaseModel):
    overall_outcome: Literal["Acceptable", "Not acceptable for DAFF assessment"] = "Not acceptable for DAFF assessment"
    critical_errors: list[ComplianceIssue] = []
    warnings: list[ComplianceIssue] = []
    fix_instructions: list[str] = []
    rules_version: str = "DAFF-2024-V1.0"
    model_version: str = "LAYOUTLM-V1"

class PackingDeclaration(BaseModel):
    """
    Flat JSON representation of a Packing Declaration.
    This is the exact payload sent to Power Automate.
    """
    file_name: Optional[str] = None
    serial_number: Optional[str] = None
    declaration_type: Optional[Literal["FCL_ANNUAL", "FCL_SINGLE", "FCL_X_SINGLE", "LCL_SINGLE", "LCL_ANNUAL", "FCX_SINGLE", "PKD_SINGLE"]] = None

    # Issuer & parties
    issuer_company: Optional[str] = None
    issuer_address: Optional[str] = None
    issuer_address_is_po_box: bool = False
    exporter: Optional[str] = None
    importer: Optional[str] = None

    # Shipment
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    consignment_ref: Optional[str] = None  # container / BL / invoice number

    # Document details
    date_issued: Optional[str] = None        # YYYY-MM-DD
    date_valid: bool = False
    signed: bool = False
    signature_type: Optional[str] = None
    printed_name: Optional[str] = None
    letterhead_present: bool = False

    # Compliance checkboxes (resolved to text)
    q1_unacceptable_material: Literal["YES", "NO", "BLANK", "NOT_FOUND", "DECLARED_BLANK"] = "BLANK"
    q2_timber_bamboo: Literal["YES_TIMBER", "YES_BAMBOO", "NO", "BLANK", "NOT_FOUND", "DECLARED_BLANK"] = "BLANK"
    q3_treatment: Literal["ISPM15", "DAFF_CERTIFIED", "NOT_TREATED", "NOT_APPLICABLE", "BLANK", "NOT_FOUND", "DECLARED_BLANK"] = "BLANK"
    q4_cleanliness: Literal["PRESENT", "ABSENT", "BLANK", "NOT_FOUND", "DECLARED_BLANK"] = "BLANK"

    # Alterations
    alterations_present: bool = False
    alterations_endorsed: bool = False

    # Extraction metadata (informational only)
    extraction_method: Literal["pdf_text", "ocr", "docx", "xlsx"] = "pdf_text"
    ocr_confidence: Optional[float] = None
    
    # Dual-Track Intelligence (V5)
    ml_predictions: Optional[dict] = None
    ml_confidence: Optional[float] = None
    field_scores: Optional[dict] = None  # map of field -> confidence
    
    # ── DETERMINISTIC COMPLIANCE REPORT (V6+) ──
    compliance_report: Optional[ComplianceReport] = None


class TripleExtraction(BaseModel):
    """
    Combined result for the 3-way comparison mechanism.
    """
    ocr: PackingDeclaration
    ml: PackingDeclaration
    pa: PackingDeclaration
    is_match: bool = False
    match_score: float = 0.0
    file_name: Optional[str] = None
