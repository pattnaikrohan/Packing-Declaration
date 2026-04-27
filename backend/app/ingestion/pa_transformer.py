"""
Power Automate AI Builder → PackingDeclaration transformer.

Converts the deeply nested OData/CRM response from Power Automate's
AI Builder Document Processing model into the flat PackingDeclaration
schema used by the OCR extraction engine.

Flow:
  1. Extract `readResults` elements → reconstruct full-page text
  2. Extract `fields` (AI Builder named fields) → map directly to schema
  3. Resolve individual checkbox fields (Q1_Yes, Q1_No, etc.) into enums
  4. Apply shared heuristic extractors on the reconstructed text as fallback
  5. Return a standard PackingDeclaration object

AI Builder Field Names (from Power Automate model):
  ─ VesselName, VoyageNumber, ConsignmentID
  ─ PrintedName, DateOfIssue
  ─ IssuerCompany, IssuerAddress
  ─ Q4_CleanStatementPresent, LetterheadPresent
  ─ Q1_Yes, Q1_No
  ─ Q2_Timber, Q2_Bamboo, Q2_No
  ─ Q3_ISPM15, Q3_DAFF, Q3_NotTreated
  ─ Signature Present
"""
import logging
import re
from typing import Any

from app.ingestion.schema import PackingDeclaration
from app.ingestion import extractors_common, compliance_engine

logger = logging.getLogger(__name__)


# ── Simple 1:1 field mapping (AI Builder name → PackingDeclaration field) ─────
# These are straightforward text fields that map directly.
SIMPLE_FIELD_MAP: dict[str, str] = {
    "VesselName":      "vessel_name",
    "VoyageNumber":    "voyage_number",
    "ConsignmentID":   "consignment_ref",
    "PrintedName":     "printed_name",
    "DateOfIssue":     "date_issued",
    "IssuerCompany":   "issuer_company",
    "IssuerAddress":   "issuer_address",
}

# ── Checkbox fields that need special boolean → enum resolution ───────────────
# These are individual checkbox selections from AI Builder.
# Each key is the AI Builder field name; each value is the group + enum value
# Format: (group_name, resolved_enum_value)
CHECKBOX_FIELD_MAP: dict[str, tuple[str, str]] = {
    # Q1: Unacceptable Packaging Material
    "Q1_Yes":           ("q1_unacceptable_material", "YES"),
    "Q1_No":            ("q1_unacceptable_material", "NO"),

    # Q2: Timber / Bamboo
    "Q2_Timber":        ("q2_timber_bamboo", "YES_TIMBER"),
    "Q2_Bamboo":        ("q2_timber_bamboo", "YES_BAMBOO"),
    "Q2_No":            ("q2_timber_bamboo", "NO"),

    # Q3: Treatment
    "Q3_ISPM15":        ("q3_treatment", "ISPM15"),
    "Q3_DAFF":          ("q3_treatment", "DAFF_CERTIFIED"),
    "Q3_NotTreated":    ("q3_treatment", "NOT_TREATED"),

    # Q4: Cleanliness Statement
    "Q4_CleanStatementPresent": ("q4_cleanliness", "PRESENT"),
    "Q4_Clean":                 ("q4_cleanliness", "PRESENT"),
    "CleanStatementPresent":    ("q4_cleanliness", "PRESENT"),
}

# ── Boolean fields ────────────────────────────────────────────────────────────
BOOLEAN_FIELD_MAP: dict[str, str] = {
    "LetterheadPresent":  "letterhead_present",
    "Signature Present":  "signed",
}


def _safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Safely navigate nested dicts/objects."""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
        if current is None:
            return default
    return current


def _is_checked(value: Any) -> bool:
    """
    Determine if an AI Builder checkbox field is selected/checked.
    AI Builder may return: bool, string ("selected"/"unselected"), 
    confidence object, or text content presence.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lower = value.strip().lower()
        return lower in ("true", "yes", "selected", "checked", "1", ":selected:")
    if isinstance(value, dict):
        # AI Builder nested field: check "value", "text", or "selectionMark"
        sel = value.get("selectionMark") or value.get("value") or value.get("text")
        # Special case: If this is a Cleanliness Statement and we have text, it's checked
        display_name = str(value.get("displayName", "")).lower()
        if "cleanstatement" in display_name or "cleanliness" in display_name:
            if isinstance(sel, str) and len(sel.strip()) > 20: # Long statement text
                return True
        
        if sel is not None:
            return _is_checked(sel)
        # Check confidence — if confidence > 0.5 and content exists, treat as checked
        conf = value.get("confidence", 0)
        content = value.get("text") or value.get("content") or value.get("value")
        if content and conf > 0.5:
            return True
    return False


def _get_field_value(field_data: Any) -> Any:
    """Extract the usable value from an AI Builder field structure."""
    if field_data is None:
        return None
    if isinstance(field_data, (str, int, float, bool)):
        return field_data
    if isinstance(field_data, dict):
        # AI Builder fields: { value: "...", text: "...", confidence: 0.95 }
        return (
            field_data.get("value")
            or field_data.get("text")
            or field_data.get("content")
        )
    return None


def _reconstruct_text_from_read_results(pa_response: dict) -> str:
    """
    Walk the readResults → elements array and reconstruct the page text
    by joining all element text values in order.
    Handles the OData-decorated CRM response structure.
    """
    prediction = _safe_get(pa_response, "body", "responsev2", "predictionOutput")
    if not prediction:
        prediction = _safe_get(pa_response, "responsev2", "predictionOutput")
    if not prediction:
        prediction = pa_response

    read_results = prediction.get("readResults", [])
    
    lines: list[str] = []
    for page in read_results:
        elements = page.get("elements", [])
        # Sort elements by vertical position (top), then horizontal (left)
        sorted_elements = sorted(
            elements,
            key=lambda e: (
                _safe_get(e, "boundingBox", "top", default=0),
                _safe_get(e, "boundingBox", "left", default=0),
            )
        )
        
        # Group elements into lines based on vertical proximity
        current_line_top = -1
        current_line_words: list[str] = []
        line_threshold = 0.012  # ~1.2% of page height tolerance for same-line grouping
        
        for elem in sorted_elements:
            text = elem.get("text", "").strip()
            if not text:
                continue
            top = _safe_get(elem, "boundingBox", "top", default=0)
            
            if current_line_top < 0 or abs(top - current_line_top) > line_threshold:
                # New line detected
                if current_line_words:
                    lines.append(" ".join(current_line_words))
                current_line_words = [text]
                current_line_top = top
            else:
                current_line_words.append(text)
        
        # Flush last line
        if current_line_words:
            lines.append(" ".join(current_line_words))
    
    return "\n".join(lines)


def _extract_ai_builder_fields(pa_response: dict) -> dict[str, Any]:
    """
    Extract named fields from the AI Builder predictionOutput.
    
    AI Builder (via Power Automate CRM/OData) places named fields in various places:
        - predictionOutput.labels.{FieldName}
        - predictionOutput.fields.labels.{FieldName}
        - predictionOutput.fields.{FieldName}
        - predictionOutput.{FieldName}
    
    This function performs a multi-strategy search to find all possible fields.
    """
    import json as _json

    prediction = _safe_get(pa_response, "body", "responsev2", "predictionOutput")
    if not prediction:
        prediction = _safe_get(pa_response, "responsev2", "predictionOutput")
    if not prediction:
        prediction = pa_response

    extracted: dict[str, Any] = {}

    def _add_fields_from_dict(d: Any):
        if not isinstance(d, dict):
            return
        for k, v in d.items():
            if k.startswith("@odata") or k.endswith("@odata.type"):
                continue
            
            # If it's a field object (has 'value', 'text', 'fieldType', or 'displayName')
            if isinstance(v, dict) and any(x in v for x in ["value", "text", "fieldType", "displayName"]):
                # Add by key
                if k not in extracted:
                    extracted[k] = v
                # Also add by displayName if different (very important for Signature hash keys)
                display_name = v.get("displayName")
                if display_name and display_name not in extracted:
                    extracted[display_name] = v
                # Special handle for Signature... hashes
                if k.startswith("Signatur") and "Signature Present" not in extracted:
                    extracted["Signature Present"] = v
            # Otherwise, if it's 'labels', 'fields', or 'tables', recurse into it
            elif k in ["labels", "fields", "tables"] and isinstance(v, dict):
                _add_fields_from_dict(v)
            # Strategy: if it's just a dict, maybe the fields are flat inside it
            # But avoid recursing into known system fields like 'readResults'
            elif k not in ["readResults", "boundingBox", "polygon"] and isinstance(v, dict):
                 # Check if this dict itself has field-like children
                 for sub_k, sub_v in v.items():
                     if isinstance(sub_v, dict) and any(x in sub_v for x in ["value", "text", "fieldType"]):
                         if sub_k not in extracted:
                             extracted[sub_k] = sub_v

    # Run recursive extraction starting from prediction output
    if isinstance(prediction, dict):
        _add_fields_from_dict(prediction)

    # ── DEBUG: Log extracted fields ───────────────────────────────────────────
    logger.warning("=" * 80)
    logger.warning(f"[PA DEBUG] EXTRACTED {len(extracted)} FIELDS FROM AI BUILDER:")
    logger.warning("=" * 80)
    if not extracted:
        logger.warning("[PA DEBUG] >>> NO FIELDS FOUND!")
        if isinstance(prediction, dict):
            logger.warning(f"[PA DEBUG] >>> Top-level keys: {list(prediction.keys())}")
    else:
        for fname, fdata in sorted(extracted.items()):
            try:
                dumped = _json.dumps(fdata, indent=2, default=str)
                if len(dumped) > 300:
                    dumped = dumped[:300] + "..."
            except Exception:
                dumped = str(fdata)[:300]
            logger.warning(f"[PA DEBUG]   '{fname}' => {dumped}")
    logger.warning("=" * 80)

    return extracted


def _map_declaration_type(raw: str | None) -> str | None:
    """Map AI Builder declaration type values to our enum."""
    if not raw:
        return None
    upper = raw.upper().replace(" ", "_").replace("-", "_")
    valid = {"FCL_ANNUAL", "FCL_SINGLE", "FCL_X_SINGLE", "LCL_SINGLE", "LCL_ANNUAL", "FCX_SINGLE", "PKD_SINGLE"}
    if upper in valid:
        return upper
    if "FCL" in upper and "ANNUAL" in upper:
        return "FCL_ANNUAL"
    if "LCL" in upper:
        return "LCL_SINGLE"
    if "FCL" in upper:
        return "FCL_SINGLE"
    return "PKD_SINGLE"


def transform_pa_response(pa_response: dict, filename: str = "unknown") -> PackingDeclaration:
    """
    Main entry point: Transform a Power Automate AI Builder response
    into a PackingDeclaration matching the OCR extraction format.
    
    Args:
        pa_response: The full JSON response from Power Automate 
                     (including statusCode, headers, body).
        filename: Original filename for metadata.
    
    Returns:
        A PackingDeclaration object identical in structure to what the
        OCR engine produces.
    """
    pkd = PackingDeclaration()
    pkd.file_name = filename
    pkd.extraction_method = "pdf_text"  # PA uses AI Builder (document intelligence)
    
    # ── Step 1: Reconstruct full text from readResults ────────────────────────
    full_text = _reconstruct_text_from_read_results(pa_response)
    logger.info(f"[PA Transformer] Reconstructed {len(full_text)} chars from readResults")
    
    # ── Step 2: Extract AI Builder named fields ──────────────────────────────
    ai_fields = _extract_ai_builder_fields(pa_response)
    logger.info(f"[PA Transformer] Extracted {len(ai_fields)} AI Builder fields: {list(ai_fields.keys())}")
    
    # ── Step 3a: Map simple text fields → PackingDeclaration ─────────────────
    for ai_name, pkd_field in SIMPLE_FIELD_MAP.items():
        if ai_name in ai_fields:
            value = _get_field_value(ai_fields[ai_name])
            if value is not None and str(value).strip():
                value = str(value).strip()
                # Special handling for declaration_type
                if pkd_field == "declaration_type":
                    pkd.declaration_type = _map_declaration_type(value)
                # Special handling for date validation
                elif pkd_field == "date_issued":
                    pkd.date_issued, pkd.date_valid = extractors_common.extract_date(value)
                    if not pkd.date_issued: # Fallback if validation failed
                         pkd.date_issued = value
                else:
                    setattr(pkd, pkd_field, value)
                logger.debug(f"[PA Transformer] {ai_name} → {pkd_field} = {getattr(pkd, pkd_field, value)}")
    
    # ── Step 3b: Resolve checkbox fields → enum values ───────────────────────
    # Checkboxes come as individual boolean fields (Q1_Yes, Q1_No, etc.)
    # We need to determine which one is checked and resolve to the enum value
    
    # Group checkboxes by their target enum field
    checkbox_groups: dict[str, list[tuple[str, str, bool]]] = {}
    for ai_name, (group, enum_val) in CHECKBOX_FIELD_MAP.items():
        if ai_name in ai_fields:
            checked = _is_checked(ai_fields[ai_name])
            if group not in checkbox_groups:
                checkbox_groups[group] = []
            checkbox_groups[group].append((ai_name, enum_val, checked))
            logger.debug(f"[PA Transformer] Checkbox {ai_name} → checked={checked}")
    
    # Resolve each checkbox group to a single enum value
    for group_field, options in checkbox_groups.items():
        # Find which checkbox(es) are checked
        checked_options = [(name, val) for name, val, chk in options if chk]
        
        if len(checked_options) == 1:
            # Exactly one checked — perfect resolution
            setattr(pkd, group_field, checked_options[0][1])
            logger.info(f"[PA Transformer] {group_field} resolved → {checked_options[0][1]} "
                        f"(via {checked_options[0][0]})")
        elif len(checked_options) > 1:
            # Multiple checked — take the first one and warn
            setattr(pkd, group_field, checked_options[0][1])
            logger.warning(f"[PA Transformer] {group_field}: Multiple checkboxes selected "
                           f"{[c[0] for c in checked_options]} — using {checked_options[0][1]}")
        else:
            # None checked — leave as BLANK (default)
            logger.info(f"[PA Transformer] {group_field}: No checkbox selected → BLANK")
    
    # ── Step 3c: Resolve boolean fields ──────────────────────────────────────
    for ai_name, pkd_field in BOOLEAN_FIELD_MAP.items():
        if ai_name in ai_fields:
            checked = _is_checked(ai_fields[ai_name])
            setattr(pkd, pkd_field, checked)
            logger.debug(f"[PA Transformer] {ai_name} → {pkd_field} = {checked}")
    
    # ── Step 4: Heuristic fallbacks from reconstructed text ──────────────────
    # Only apply if the AI Builder didn't provide the field
    if full_text:
        if not pkd.declaration_type:
            pkd.declaration_type = extractors_common.detect_declaration_type(full_text)
        
        if not pkd.issuer_company:
            pkd.issuer_company = extractors_common.extract_company(full_text)
        
        if not pkd.issuer_address:
            addr, is_po = extractors_common.extract_address(full_text)
            pkd.issuer_address = addr
            pkd.issuer_address_is_po_box = is_po
        
        if not pkd.vessel_name:
            pkd.vessel_name = extractors_common.extract_vessel(full_text)
        
        if not pkd.voyage_number:
            pkd.voyage_number = extractors_common.extract_voyage(full_text)
        
        if not pkd.consignment_ref:
            ref, _ = extractors_common.extract_consignment_link(full_text)
            pkd.consignment_ref = ref
        
        if not pkd.date_issued:
            dt, valid = extractors_common.extract_date(full_text)
            pkd.date_issued = dt
            pkd.date_valid = valid
        
        if not pkd.printed_name:
            pkd.printed_name = extractors_common.extract_printed_name(full_text)
        
        # Signature detection (only if PA didn't provide it)
        if not pkd.signed:
            signed, sig_type = extractors_common.detect_signature(full_text)
            pkd.signed = signed
            pkd.signature_type = sig_type
        
        # Letterhead (only if PA didn't provide it)
        if not pkd.letterhead_present:
            pkd.letterhead_present = extractors_common.detect_letterhead(full_text)
        
        # Alterations
        alt_present, alt_endorsed = extractors_common.detect_alterations(full_text)
        pkd.alterations_present = alt_present
        pkd.alterations_endorsed = alt_endorsed
    
    # ── Step 5: Extract confidence metadata ──────────────────────────────────
    prediction = _safe_get(pa_response, "body", "responsev2", "predictionOutput")
    if not prediction:
        prediction = _safe_get(pa_response, "responsev2", "predictionOutput")
    if prediction:
        confidence = prediction.get("layoutConfidenceScore")
        if confidence is not None:
            pkd.ocr_confidence = float(confidence)
    
    # ── Step 6: Apply compliance engine ──────────────────────────────────────
    pkd.compliance_report = compliance_engine.evaluate_compliance(pkd)
    
    # ── PRINT FINAL RESULT ────────────────────────────────────────────────────
    import json as _json
    result_dict = pkd.model_dump() if hasattr(pkd, 'model_dump') else pkd.dict()
    # Remove verbose compliance_report for cleaner output
    result_dict.pop("compliance_report", None)
    print("\n" + "=" * 80)
    print("[PA TRANSFORMER] FINAL RESULT:")
    print("=" * 80)
    print(_json.dumps(result_dict, indent=2, default=str))
    print("=" * 80 + "\n")
    # ── END PRINT ─────────────────────────────────────────────────────────────
    
    return pkd
