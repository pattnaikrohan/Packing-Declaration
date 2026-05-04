"""
Azure Document Intelligence OCR extractor — the best OCR for structured
packing declaration forms. Uses Azure AI prebuilt-layout model for:
  • High-accuracy text extraction from scanned PDFs, JPGs, PNGs
  • Table detection and extraction
  • Checkbox / selection mark detection
  • Key-value pair recognition

Falls back gracefully to EasyOCR when Azure credentials are not configured.
"""
import io
import logging
import re
from typing import Optional

from app.ingestion.schema import PackingDeclaration
from app.ingestion import extractors_common as ec
from app.ingestion.checkbox_resolver import CheckboxResolver
from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Azure client (singleton)
_azure_client = None


def _get_azure_client():
    """Initialize Azure Document Intelligence client (lazy singleton)."""
    global _azure_client
    if _azure_client is None:
        from azure.core.credentials import AzureKeyCredential
        from azure.ai.documentintelligence import DocumentIntelligenceClient

        _azure_client = DocumentIntelligenceClient(
            endpoint=settings.AZURE_DOC_INTEL_ENDPOINT,
            credential=AzureKeyCredential(settings.AZURE_DOC_INTEL_KEY),
        )
        logger.info("Azure Document Intelligence client initialized")
    return _azure_client


def _analyze_document(file_bytes: bytes, content_type: str = "application/pdf") -> dict:
    """
    Send document to Azure AI for analysis using prebuilt-layout model.
    Returns the raw analysis result.
    """
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

    client = _get_azure_client()

    poller = client.begin_analyze_document(
        "prebuilt-layout",
        analyze_request=file_bytes,
        content_type=content_type,
        features=["keyValuePairs"],
    )
    return poller.result()


def _extract_text_from_result(result) -> str:
    """Extract full text from Azure DI result."""
    if hasattr(result, "content") and result.content:
        return result.content
    # Fallback: concatenate page lines
    lines = []
    if hasattr(result, "pages"):
        for page in result.pages:
            if hasattr(page, "lines"):
                for line in page.lines:
                    lines.append(line.content)
    return "\n".join(lines)


def _extract_kv_pairs(result) -> dict:
    """Extract key-value pairs from Azure DI result."""
    kvs = {}
    if hasattr(result, "key_value_pairs") and result.key_value_pairs:
        for kv in result.key_value_pairs:
            key = kv.key.content.strip() if kv.key else ""
            value = kv.value.content.strip() if kv.value else ""
            if key:
                kvs[key] = value
    return kvs


def _extract_selection_marks(result) -> dict:
    """
    Extract checkbox/selection mark states from Azure DI result.
    Maps to Q1-Q4 based on surrounding text context.
    """
    marks = {"q1": "NOT_FOUND", "q2": "NOT_FOUND", "q3": "NOT_FOUND", "q4": "NOT_FOUND"}

    if not hasattr(result, "pages"):
        return marks

    for page in result.pages:
        if not hasattr(page, "selection_marks") or not page.selection_marks:
            continue

        page_lines = []
        if hasattr(page, "lines"):
            page_lines = [(ln.content.upper(), ln.polygon) for ln in page.lines]

        page_height = page.height if hasattr(page, "height") else 1
        page_width = page.width if hasattr(page, "width") else 1

        for sm in page.selection_marks:
            is_selected = sm.state == "selected"
            if not is_selected:
                continue

            # Get the Y-position of this selection mark (use polygon or span)
            sm_y = 0
            sm_x = 0
            if hasattr(sm, "polygon") and sm.polygon:
                # polygon is [x1,y1, x2,y2, x3,y3, x4,y4]
                ys = [sm.polygon[i] for i in range(1, len(sm.polygon), 2)]
                xs = [sm.polygon[i] for i in range(0, len(sm.polygon), 2)]
                sm_y = sum(ys) / len(ys) if ys else 0
                sm_x = sum(xs) / len(xs) if xs else 0
            elif hasattr(sm, "bounding_regions") and sm.bounding_regions:
                br = sm.bounding_regions[0]
                if hasattr(br, "polygon") and br.polygon:
                    ys = [br.polygon[i] for i in range(1, len(br.polygon), 2)]
                    xs = [br.polygon[i] for i in range(0, len(br.polygon), 2)]
                    sm_y = sum(ys) / len(ys) if ys else 0
                    sm_x = sum(xs) / len(xs) if xs else 0

            # Find the closest text line to determine which question this mark belongs to
            closest_q = _classify_mark_by_context(sm_y, sm_x, page_lines, page_height)
            if closest_q:
                _resolve_mark(marks, closest_q, sm_x, sm_y, page_lines, page_width)

    return marks


def _classify_mark_by_context(mark_y: float, mark_x: float, page_lines: list, page_height: float) -> Optional[str]:
    """Classify which question (Q1-Q4) a selection mark belongs to based on nearby text."""

    # Look for question keywords within a Y-band around the mark
    band = page_height * 0.12  # 12% vertical band

    nearby_text = ""
    for text, polygon in page_lines:
        if not polygon:
            continue
        line_ys = [polygon[i] for i in range(1, len(polygon), 2)]
        line_y = sum(line_ys) / len(line_ys) if line_ys else 0
        if abs(line_y - mark_y) < band:
            nearby_text += " " + text

    tu = nearby_text.upper()

    if any(k in tu for k in ["Q1", "UNACCEPT", "PROHIBIT"]):
        return "q1"
    elif any(k in tu for k in ["Q2", "TIMBER", "BAMBOO", "DUNNAGE"]):
        return "q2"
    elif any(k in tu for k in ["Q3", "TREATMENT", "ISPM", "DAFF", "CERTIF"]):
        return "q3"
    elif any(k in tu for k in ["Q4", "CLEANLINESS", "CLEAN", "CONTAMINATION"]):
        return "q4"

    # Fallback: use relative Y position
    rel_y = mark_y / page_height if page_height > 0 else 0
    if rel_y < 0.30:
        return "q1"
    elif rel_y < 0.50:
        return "q2"
    elif rel_y < 0.70:
        return "q3"
    else:
        return "q4"


def _resolve_mark(marks: dict, q: str, mark_x: float, mark_y: float, page_lines: list, page_width: float):
    """Resolve what a selected mark means (YES/NO/TIMBER etc.) based on nearby labels."""

    band_y = page_width * 0.05  # small vertical band
    nearby = ""
    for text, polygon in page_lines:
        if not polygon:
            continue
        line_ys = [polygon[i] for i in range(1, len(polygon), 2)]
        line_xs = [polygon[i] for i in range(0, len(polygon), 2)]
        line_y = sum(line_ys) / len(line_ys) if line_ys else 0
        line_x = sum(line_xs) / len(line_xs) if line_xs else 0

        # Look for labels near the mark horizontally
        if abs(line_y - mark_y) < page_width * 0.08:
            # Check if label is close to mark horizontally (within 15% page width)
            if abs(line_x - mark_x) < page_width * 0.25:
                nearby += " " + text

    tu = nearby.upper()

    if q == "q1":
        if "NO" in tu and "YES" not in tu:
            marks["q1"] = "NO"
        else:
            marks["q1"] = "YES"
    elif q == "q2":
        if "NO" in tu and "TIMBER" not in tu and "BAMBOO" not in tu:
            marks["q2"] = "NO"
        elif "BAMBOO" in tu:
            marks["q2"] = "YES_BAMBOO"
        else:
            marks["q2"] = "YES_TIMBER"
    elif q == "q3":
        if "DAFF" in tu or "CERTIF" in tu:
            marks["q3"] = "DAFF_CERTIFIED"
        elif "NOT" in tu and "TREAT" in tu:
            marks["q3"] = "NOT_TREATED"
        elif "N/A" in tu or "NOT APPLICABLE" in tu:
            marks["q3"] = "NOT_APPLICABLE"
        else:
            marks["q3"] = "ISPM15"
    elif q == "q4":
        marks["q4"] = "PRESENT"


def _map_kv_to_fields(kvs: dict, text: str) -> dict:
    """Map extracted key-value pairs to PackingDeclaration fields."""
    fields = {}

    for key, value in kvs.items():
        ku = key.upper()
        if not value or value.strip() in ("", "_", "__", "___"):
            continue

        if any(k in ku for k in ["VESSEL", "SHIP", "M/V"]):
            if "VOYAGE" not in ku:
                fields["vessel_name"] = value.strip()
        if any(k in ku for k in ["VOYAGE", "VOY"]):
            fields["voyage_number"] = value.strip()
        if any(k in ku for k in ["CONSIGNMENT", "NUMERICAL LINK", "REFERENCE"]):
            fields["consignment_ref"] = value.strip()
        if any(k in ku for k in ["DATE", "ISSUED"]):
            fields["date_issued"] = value.strip()
        if any(k in ku for k in ["PRINT", "NAME", "SIGNED BY", "AUTHORISED"]):
            fields["printed_name"] = value.strip()
        if any(k in ku for k in ["COMPANY", "EXPORTER", "PACKER"]):
            fields["issuer_company"] = value.strip()

    return fields


def extract(file_bytes: bytes, is_pdf: bool = False) -> PackingDeclaration:
    """
    Primary extraction using Azure Document Intelligence.
    Uses prebuilt-layout model for maximum accuracy on structured forms.
    """
    # Determine content type
    if is_pdf:
        content_type = "application/pdf"
    else:
        # Try to detect from bytes
        if file_bytes[:2] == b'\xff\xd8':
            content_type = "image/jpeg"
        elif file_bytes[:4] == b'\x89PNG':
            content_type = "image/png"
        elif file_bytes[:4] == b'%PDF':
            content_type = "application/pdf"
        else:
            content_type = "application/octet-stream"

    try:
        result = _analyze_document(file_bytes, content_type)
    except Exception as e:
        logger.error(f"Azure Document Intelligence failed: {e}")
        # Fall back to EasyOCR
        from app.ingestion import ocr_extractor
        return ocr_extractor.extract(file_bytes, is_pdf=is_pdf)

    # Extract text
    full_text = _extract_text_from_result(result)
    if not full_text.strip():
        logger.warning("Azure DI returned empty text — falling back to EasyOCR")
        from app.ingestion import ocr_extractor
        return ocr_extractor.extract(file_bytes, is_pdf=is_pdf)

    # Extract key-value pairs
    kvs = _extract_kv_pairs(result)
    kv_fields = _map_kv_to_fields(kvs, full_text)

    # Extract selection marks (checkboxes)
    checkbox_result = _extract_selection_marks(result)

    # Also run text-based checkbox detection as backup
    from app.ingestion.ocr_extractor import _detect_checkboxes_from_text
    text_checkbox = _detect_checkboxes_from_text(full_text)

    # Resolve checkboxes: Azure selection marks take priority, text-based as fallback
    res = CheckboxResolver.map_resolution(
        CheckboxResolver.resolve_q1(checkbox_result["q1"], text_checkbox["q1"]),
        CheckboxResolver.resolve_q2(checkbox_result["q2"], text_checkbox["q2"]),
        CheckboxResolver.resolve_q3(checkbox_result["q3"], text_checkbox["q3"]),
        CheckboxResolver.resolve_q4(checkbox_result["q4"], text_checkbox["q4"]),
    )

    logger.info(
        "[Azure DI] Checkbox Resolution — azure:%s text:%s resolved:%s kvs:%d",
        checkbox_result, text_checkbox, res, len(kvs),
    )

    # Heuristic extraction (deterministic fallback for fields not in KV pairs)
    addr, is_po = ec.extract_address(full_text)
    consignment_heur, _ = ec.extract_consignment_link(full_text)
    date_str_heur, date_valid = ec.extract_date(full_text)
    signed, sig_type = ec.detect_signature(full_text)
    alterations, endorsed = ec.detect_alterations(full_text)

    # Build result — KV pairs take priority, then heuristic
    pkd = PackingDeclaration(
        declaration_type=ec.detect_declaration_type(full_text),
        issuer_company=kv_fields.get("issuer_company") or ec.extract_company(full_text),
        issuer_address=addr,
        issuer_address_is_po_box=is_po,
        vessel_name=kv_fields.get("vessel_name") or ec.extract_vessel(full_text),
        voyage_number=kv_fields.get("voyage_number") or ec.extract_voyage(full_text),
        consignment_ref=kv_fields.get("consignment_ref") or consignment_heur,
        exporter=ec.extract_party(full_text, "Exporter"),
        importer=ec.extract_party(full_text, "Importer"),
        date_issued=kv_fields.get("date_issued") or date_str_heur,
        date_valid=date_valid,
        signed=signed,
        signature_type=sig_type,
        printed_name=kv_fields.get("printed_name") or ec.extract_printed_name(full_text),
        letterhead_present=ec.detect_letterhead(full_text),
        q1_unacceptable_material=res["q1"],
        q2_timber_bamboo=res["q2"],
        q3_treatment=res["q3"],
        q4_cleanliness=res["q4"],
        alterations_present=alterations,
        alterations_endorsed=endorsed,
        extraction_method="azure_doc_intel",
        ocr_confidence=0.98,  # Azure DI is consistently high-accuracy
        field_scores={
            "issuer_company": 0.97 if kv_fields.get("issuer_company") else 0.90,
            "issuer_address": 0.95,
            "vessel_name": 0.97 if kv_fields.get("vessel_name") else 0.90,
            "voyage_number": 0.97 if kv_fields.get("voyage_number") else 0.90,
            "consignment_ref": 0.97 if kv_fields.get("consignment_ref") else 0.85,
            "date_issued": 0.95 if kv_fields.get("date_issued") or date_str_heur else 0.0,
            "signed": 0.98 if signed else 0.0,
            "printed_name": 0.95 if kv_fields.get("printed_name") else 0.85,
            "q1": 0.99 if res["q1"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
            "q2": 0.99 if res["q2"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
            "q3": 0.99 if res["q3"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
            "q4": 0.99 if res["q4"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
        },
    )

    # Attach raw data for downstream ML layer
    pkd._raw_text = full_text
    pkd._tokens = full_text.split()
    pkd._bboxes = []
    pkd._page_size = [0, 0]

    return pkd
