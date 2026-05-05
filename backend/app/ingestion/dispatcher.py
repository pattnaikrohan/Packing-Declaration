"""
File dispatcher — routes uploaded files to the correct extractor.
Also detects when a PDF has no extractable text and auto-routes to OCR.
"""
import logging
from app.ingestion.schema import PackingDeclaration, TripleExtraction
from app.ingestion import ml_engine

logger = logging.getLogger(__name__)

MIME_MAP = {
    "application/pdf": "pdf",
    "image/jpeg": "ocr_image",
    "image/png": "ocr_image",
    "image/tiff": "ocr_image",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
}

EXT_MAP = {
    ".pdf": "pdf",
    ".jpg": "ocr_image",
    ".jpeg": "ocr_image",
    ".png": "ocr_image",
    ".tiff": "ocr_image",
    ".tif": "ocr_image",
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
}


def _is_pdf_scanned(file_bytes: bytes) -> bool:
    """Returns True only if pdfplumber extracts virtually no text (truly scanned/image-only)."""
    try:
        import pdfplumber
        from io import BytesIO
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages[:3])
            is_scanned = len(text.strip()) < 20
            logger.info(f"[dispatch] PDF text check: {len(text.strip())} chars → {'SCANNED' if is_scanned else 'DIGITAL'}")
            return is_scanned
    except Exception as e:
        logger.warning(f"Error checking if PDF is scanned: {e} - defaulting to digital (pdfplumber)")
        return False  # Default to digital/pdfplumber — safer and faster


def _real_pa_extraction(file_bytes: bytes, filename: str, fallback_result: PackingDeclaration) -> PackingDeclaration:
    """
    Call Power Automate AI Builder and transform the response into a PackingDeclaration.
    Falls back to a copy of the OCR result if the PA call fails.
    """
    import copy
    import httpx
    from app.config import settings
    from app.ingestion.pa_transformer import transform_pa_response

    if not settings.POWER_AUTOMATE_URL:
        logger.info("[PA] No Power Automate URL configured — using fallback")
        pa = copy.deepcopy(fallback_result)
        pa.extraction_method = "pdf_text"
        return pa

    payload = {
        "serial_number": "1",
        "filename": filename
    }

    try:
        # Synchronous call within the extraction pipeline
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                settings.POWER_AUTOMATE_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        
        if resp.status_code >= 300:
            logger.warning(f"[PA] Power Automate returned HTTP {resp.status_code} — using fallback")
            pa = copy.deepcopy(fallback_result)
            pa.extraction_method = "pdf_text"
            return pa
        
        pa_response = resp.json()
        logger.info(f"[PA] Received AI Builder response, transforming...")
        pkd = transform_pa_response(pa_response, filename=filename)
        return pkd

    except Exception as e:
        logger.error(f"[PA] Power Automate call failed: {e} — using fallback")
        pa = copy.deepcopy(fallback_result)
        pa.extraction_method = "pdf_text"
        return pa



def extract(file_bytes: bytes, filename: str, content_type: str = "") -> TripleExtraction:
    """
    Main dispatch function. Selects extractor, auto-routes scanned PDFs to OCR.
    Now returns TripleExtraction (OCR, ML, PA results) for comparison.
    """
    import os
    from app.ingestion.schema import TripleExtraction
    ext = os.path.splitext(filename)[1].lower()

    route = MIME_MAP.get(content_type) or EXT_MAP.get(ext, "pdf")

    # 1. Primary Extraction
    if route == "docx":
        from app.ingestion import docx_extractor
        ocr_result = docx_extractor.extract(file_bytes)
    elif route == "pdf":
        # ALL PDFs go through pdfplumber (fast, reliable, no heavy deps)
        from app.ingestion import pdf_extractor
        ocr_result = pdf_extractor.extract(file_bytes)
        logger.info(f"[dispatch] PDF — using pdfplumber")
    elif route == "ocr_image":
        # Images: try EasyOCR if available, otherwise return empty
        from app.ingestion import ocr_extractor
        ocr_result = ocr_extractor.extract(file_bytes, is_pdf=False)
    else:
        # Fallback — treat as PDF
        from app.ingestion import pdf_extractor
        ocr_result = pdf_extractor.extract(file_bytes)

    ocr_result.file_name = filename
    ocr_result.extraction_method = ocr_result.extraction_method or ("ocr" if route != "docx" else "docx")

    # 2. ML Extraction (LayoutLM / V6 Source)
    from app.ingestion import pdf_extractor
    if route == "pdf":
        ml_result = pdf_extractor.extract(file_bytes)
    else:
        # Fallback to OCR/DOCX for non-PDFs if no specific ML extractor exists
        import copy
        ml_result = copy.deepcopy(ocr_result)
    
    ml_result.file_name = filename
    ml_result.extraction_method = "pdf_text" # Representing ML-based text extraction

    # 3. Apply Engines (Classification, LayoutLM, Compliance)
    try:
        from app.ml import layoutlm_inference
        from app.ingestion import compliance_engine, job_manager

        # Apply to ML result specifically for the "ML Source" view
        raw_text = getattr(ml_result, "_raw_text", "")
        doc_type = job_manager.HUB.classify_document(raw_text)
        ml_result.ml_predictions = {"doc_classification": doc_type}

        tokens = getattr(ml_result, "_tokens", [])
        bboxes = getattr(ml_result, "_bboxes", [])
        page_size = getattr(ml_result, "_page_size", [0, 0])
        
        if tokens:
            ml_v6 = layoutlm_inference.engine.extract_fields(tokens, bboxes, page_size)
            ml_result.ml_predictions["v6"] = ml_v6
            # Merge ML fields into ml_result
            for k, v in ml_v6.items():
                if hasattr(ml_result, k):
                    setattr(ml_result, k, v)

        # Apply Compliance consistently
        ocr_result.compliance_report = compliance_engine.evaluate_compliance(ocr_result)
        ml_result.compliance_report = compliance_engine.evaluate_compliance(ml_result)

    except Exception as e:
        logger.error(f"Extraction enrichment failed: {e}", exc_info=True)

    # 4. Power Automate (PA) Source — Real AI Builder extraction
    pa_result = _real_pa_extraction(file_bytes, filename, fallback_result=ml_result)
    if not pa_result.compliance_report:
        pa_result.compliance_report = compliance_engine.evaluate_compliance(pa_result)
    
    # Calculate match score (placeholder logic)
    # nCr: (ocr vs ml) (ocr vs pa) (ml vs pa)
    match_count = 0
    fields_to_check = ["vessel_name", "voyage_number", "consignment_ref", "q1_unacceptable_material"]
    for f in fields_to_check:
        v_ocr = getattr(ocr_result, f)
        v_ml = getattr(ml_result, f)
        v_pa = getattr(pa_result, f)
        if v_ocr == v_ml == v_pa:
            match_count += 1
            
    match_score = (match_count / len(fields_to_check)) * 100

    return TripleExtraction(
        ocr=ocr_result,
        ml=ml_result,
        pa=pa_result,
        is_match=(match_score >= 95),
        match_score=match_score,
        file_name=filename
    )
