"""
Digital PDF extractor using pdfplumber.
Handles text-based PDFs with embedded fonts and AcroForm checkboxes.
"""
import pdfplumber
from io import BytesIO
from app.ingestion.schema import PackingDeclaration
from app.ingestion import extractors_common as ec


def _detect_checkbox_from_text(text: str) -> dict:
    """
    Scan Unicode checkbox characters in text.
    ☑ (U+2611) or ☒ (U+2612) = ticked (YES)
    ☐ (U+2610) = unticked (NO)
    """
    ticked = set()
    unticked = set()

    lines = text.split("\n")
    for i, line in enumerate(lines):
        is_ticked = "☑" in line or "☒" in line
        is_untick = "☐" in line
        context = " ".join(lines[max(0, i - 1): i + 2]).upper()

        if "Q1" in context or "UNACCEPTABLE" in context or "PROHIBITED" in context:
            if is_ticked:
                ticked.add("q1")
            elif is_untick:
                unticked.add("q1")

        if "Q2" in context or "TIMBER" in context or "BAMBOO" in context:
            if is_ticked:
                ticked.add("q2_timber" if "BAMBOO" not in context else "q2_bamboo")
            elif is_untick:
                unticked.add("q2")

        if "Q3" in context or "TREATMENT" in context or "ISPM" in context or "DAFF" in context:
            if is_ticked:
                ticked.add("q3")
            elif is_untick:
                unticked.add("q3")

        if "Q4" in context or "CLEANLINESS" in context or "CLEAN" in context:
            if is_ticked:
                ticked.add("q4")
            elif is_untick:
                unticked.add("q4")

    return {"ticked": ticked, "unticked": unticked}


def _map_checkboxes(ticked: set, unticked: set) -> dict:
    q1 = "YES" if "q1" in ticked else ("NO" if "q1" in unticked else "BLANK")

    if "q2_timber" in ticked:
        q2 = "YES_TIMBER"
    elif "q2_bamboo" in ticked:
        q2 = "YES_BAMBOO"
    elif "q2" in unticked:
        q2 = "NO"
    else:
        q2 = "BLANK"

    if "q3" in ticked:
        q3 = "ISPM15"
    elif "q3" in unticked:
        q3 = "NOT_TREATED"
    else:
        q3 = "BLANK"

    q4 = "PRESENT" if "q4" in ticked else "ABSENT"
    return {"q1": q1, "q2": q2, "q3": q3, "q4": q4}


def _extract_acroform(pdf) -> dict:
    """Extract checkbox states from AcroForm fields."""
    result = {"q1": "BLANK", "q2": "BLANK", "q3": "BLANK", "q4": "ABSENT"}
    try:
        for page in pdf.pages:
            for annot in (page.annots or []):
                ft = (annot.get("FT") or "").strip("/")
                v = (annot.get("V") or "").strip("/").upper()
                name = (annot.get("T") or "").lower()
                if ft != "Btn":
                    continue
                ticked = v not in ("OFF", "NO", "", "N")
                if "q1" in name or "unacceptable" in name or "prohibited" in name:
                    result["q1"] = "YES" if ticked else "NO"
                elif "timber" in name:
                    result["q2"] = "YES_TIMBER" if ticked else "NO"
                elif "bamboo" in name:
                    result["q2"] = "YES_BAMBOO" if ticked else result["q2"]
                elif "q2" in name:
                    if ticked:
                        result["q2"] = "YES_TIMBER"
                    elif result["q2"] == "BLANK":
                        result["q2"] = "NO"
                elif "q3" in name or "treatment" in name or "ispm" in name:
                    if "ispm" in name:
                        result["q3"] = "ISPM15" if ticked else result["q3"]
                    elif "daff" in name:
                        result["q3"] = "DAFF_CERTIFIED" if ticked else result["q3"]
                    elif "not" in name or "un" in name:
                        result["q3"] = "NOT_TREATED" if ticked else result["q3"]
                    elif "na" in name or "applicable" in name:
                        result["q3"] = "NOT_APPLICABLE" if ticked else result["q3"]
                    else:
                        result["q3"] = "ISPM15" if ticked else result["q3"]
                elif "q4" in name or "cleanliness" in name:
                    result["q4"] = "PRESENT" if ticked else "ABSENT"
    except Exception:
        pass
    return result


def extract(file_bytes: bytes) -> PackingDeclaration:
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

        # Fallback 1: if pdfplumber gets no text, try PyMuPDF text extraction
        if len(full_text.strip()) < 20:
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                fitz_text = "\n".join(page.get_text() for page in doc)
                
                # Fallback 2: if still no text, use PyMuPDF OCR (Tesseract)
                if len(fitz_text.strip()) < 20:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info("[pdf_extractor] Scanned PDF detected — running PyMuPDF OCR with Tesseract")
                    ocr_pages = []
                    for page in doc:
                        try:
                            tp = page.get_textpage_ocr(language="eng", dpi=300, full=True)
                            ocr_pages.append(page.get_text("text", textpage=tp))
                        except Exception as ocr_err:
                            logger.warning(f"[pdf_extractor] Page OCR failed: {ocr_err}")
                            ocr_pages.append("")
                    ocr_text = "\n".join(ocr_pages)
                    if len(ocr_text.strip()) > len(fitz_text.strip()):
                        fitz_text = ocr_text
                
                doc.close()
                if len(fitz_text.strip()) > len(full_text.strip()):
                    full_text = fitz_text
            except Exception:
                pass

        acro = _extract_acroform(pdf)
        unicode_cb = _detect_checkbox_from_text(full_text)
        cb = _map_checkboxes(unicode_cb["ticked"], unicode_cb["unticked"])

        q1 = acro["q1"] if acro["q1"] != "BLANK" else cb["q1"]
        q2 = acro["q2"] if acro["q2"] != "BLANK" else cb["q2"]
        q3 = acro["q3"] if acro["q3"] != "BLANK" else cb["q3"]
        # q4: AcroForm wins; fall back to unicode checkbox detection
        q4 = acro["q4"] if acro["q4"] == "PRESENT" else cb["q4"]

    addr, is_po = ec.extract_address(full_text)
    consignment, _ = ec.extract_consignment_link(full_text)
    date_str, date_valid = ec.extract_date(full_text)
    signed, sig_type = ec.detect_signature(full_text)
    alterations, endorsed = ec.detect_alterations(full_text)

    return PackingDeclaration(
        declaration_type=ec.detect_declaration_type(full_text),
        issuer_company=ec.extract_company(full_text),
        issuer_address=addr,
        issuer_address_is_po_box=is_po,
        vessel_name=ec.extract_vessel(full_text),
        voyage_number=ec.extract_voyage(full_text),
        consignment_ref=consignment,
        exporter=ec.extract_party(full_text, "Exporter"),
        importer=ec.extract_party(full_text, "Importer"),
        date_issued=date_str,
        date_valid=date_valid,
        signed=signed,
        signature_type=sig_type,
        printed_name=ec.extract_printed_name(full_text),
        letterhead_present=ec.detect_letterhead(full_text),
        q1_unacceptable_material=q1,
        q2_timber_bamboo=q2,
        q3_treatment=q3,
        q4_cleanliness=q4,
        alterations_present=alterations,
        alterations_endorsed=endorsed,
        extraction_method="pdf_text",
        ocr_confidence=1.0,
    )
