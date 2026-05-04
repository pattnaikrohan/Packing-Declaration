"""
Shared regex patterns and field extractors reused across pdf/docx/xlsx extractors.
"""
import re
from datetime import datetime, date
from thefuzz import process, fuzz


# ── Declaration type detection ────────────────────────────────────────────────

TYPE_PATTERNS = [
    (r"FCL[\s\-]*/[\s\-]*X[\s\-]*PACKING", "FCL_X_SINGLE"),
    (r"FCL[\s\-]*ANNUAL", "FCL_ANNUAL"),
    (r"FCL[\s\-]*PACKING[\s\-]*(?:DECLARATION|CERTIFICATE)", "FCL_SINGLE"),
    (r"FCL[\s\-]*SINGLE", "FCL_SINGLE"),
    (r"LCL[\s\-]*ANNUAL", "LCL_ANNUAL"),
    (r"LCL[\s\-]*PACKING[\s\-]*(?:DECLARATION|CERTIFICATE)", "LCL_SINGLE"),
    (r"LCL[\s\-]*SINGLE", "LCL_SINGLE"),
    (r"FCX[\s\-]*SINGLE", "FCX_SINGLE"),
    (r"FULL\s+CONTAINER.{0,20}ANNUAL", "FCL_ANNUAL"),
    (r"FULL\s+CONTAINER.{0,20}(?:SINGLE|PACKING)", "FCL_SINGLE"),
    (r"LESS\s+CONTAINER", "LCL_SINGLE"),
    # Catch-all: plain PACKING DECLARATION with no type prefix
    (r"PACKING\s+DECLARATION", "PKD_SINGLE"),
]

def detect_declaration_type(text: str) -> str | None:
    upper = text.upper()
    for pattern, dtype in TYPE_PATTERNS:
        if re.search(pattern, upper):
            return dtype
    return None


# ── Meta field extraction ─────────────────────────────────────────────────────

def extract_company(text: str) -> str | None:
    # Strategy 0: Global known high-priority suppliers (deterministic fallback)
    tu = text.upper()
    if "POLYHOSE" in tu or "FAIIOSE" in tu:
        return "Polyhose India Rubber Pvt. Ltd."

    # Only search the header section - above 'PACKING DECLARATION'
    header_match = re.search(r"(?:FCL|LCL|FCX)?[^\n]*PACKING DECLARATION", text, re.IGNORECASE)
    header = text[:header_match.start()].strip() if header_match else text[:500]
    footer = text[-1200:] if len(text) > 1200 else text

    # Strategy 1: SHORT BRAND NAME at top of header (1-4 words, no boilerplate)
    # This catches logos like "Kwetta", "Polyhose", "RefinedTech" that appear alone
    header_lines = [l.strip() for l in header.split('\n') if l.strip()]
    for line in header_lines[:6]:
        if re.search(r'(MUST be issued|packer|supplier|goods|address|letterhead|consignment|vessel|voyage|UNACCEPTABLE|Q1|DECLARATION|DATE|PAGE|www\.|FCL|LCL)', line, re.I):
            continue
        words = line.split()
        if not (1 <= len(words) <= 4):
            continue
        # Must start with uppercase letter (real brand names do)
        if not line[0].isupper():
            continue
        # Must not be all-lowercase or pure punctuation/noise
        if not any(c.isupper() for c in line):
            continue
        # Must not be an address line
        if re.search(r'(DISTRICT|PROVINCE|CITY|STREET|ROAD|CHINA|AUSTRALIA|NEW ZEALAND|P\.O\.|BOX|ZONE|AREA)', line, re.I):
            continue
        # Must not be just punctuation or a trailing comma/period artefact
        clean = re.sub(r'[^A-Za-z0-9]', '', line)
        if len(clean) < 3:
            continue
        # Length guardrails
        if len(line) < 3 or len(line) > 50:
            continue
        return line.strip()

    # Strategy 2: Lines with corporate suffix keywords (Scan header first, then footer)
    lines = header_lines
    lines += [l.strip() for l in footer.split('\n') if l.strip()]
    
    # Priority matches: Pvt Ltd / Inc / Corp
    for line in lines:
        if re.search(r'(MUST be issued|packer|supplier|goods|address|letterhead|consignment|vessel|voyage|UNACCEPTABLE|Q1)', line, re.I):
            continue
        if re.search(r'(PVT\.?\s*LTD\.?|PTY\.?\s*LTD\.?|SDN\.?\s*BHD\.?|CO\.?\s*LTD\.?|PRIVATE\s+LIMITED)', line, re.I):
            cleaned = re.sub(r'^[^A-Za-z]+', '', line).strip()
            cleaned = re.sub(r'[\._\-\s=]{2,}$', '', cleaned).strip()
            # Fuzzy Correction for known OCR misreads
            if "faiiose" in cleaned.lower(): return "Polyhose India Rubber Pvt. Ltd."
            if len(cleaned) > 5:
                return cleaned

    # Secondary matches: Generic corporate suffixes
    for line in lines:
        if re.search(r'(MUST be issued|packer|supplier|goods|address|letterhead|consignment|vessel|voyage|UNACCEPTABLE|Q1)', line, re.I):
            continue
        if re.search(r'(LTD\.?|INC|CORP|BHD|COMPANY|GROUP|ENTERPRISE|TRADING|TECHNOLOGIES|INDUSTRIES|SOLUTIONS|SERVICES|CHEMICALS|LOGISTICS)', line, re.I):
            cleaned = re.sub(r'^[^A-Za-z]+', '', line).strip()
            cleaned = re.sub(r'[\._\-\s=]{2,}$', '', cleaned).strip()
            if len(cleaned) > 5:
                return cleaned

    return None


def extract_address(text: str) -> tuple[str | None, bool]:
    """
    Returns (address_string, is_po_box).
    Only searches header section (above the first 'PACKING DECLARATION' heading).
    """
    # Expanded form body boundaries to handle OCR noise
    boundary_patterns = [
        r"UNACCEPTABLE\s+PAC?K(?:AGING|ING)",
        r"(?:FCL|LCL|FCX)?\s*PACKING\s+DECLARATION\s*\n",
        r"Q1[\s_]+Have",
        r"TIMBER/BAMBOO",
        r"A[1234][\s_]+",
        r"ISPM\s*15",
        r"Cleanliness\s+Declaration"
    ]
    boundary_match = None
    for bp in boundary_patterns:
        m = re.search(bp, text, re.IGNORECASE)
        if m and (not boundary_match or m.start() < boundary_match.start()):
            boundary_match = m

    header = text[:boundary_match.start()].strip() if boundary_match else text[:1000]
    footer = text[-1200:] if len(text) > 1200 else ""
    header_lines = [l.strip() for l in header.split('\n') if l.strip()]
    footer_lines = [l.strip() for l in footer.split('\n') if l.strip()]

    # Priority 1: Geographic keywords
    geo_keywords = (
        r'INDUSTRIAL|AREA|VILLAGE|TOWN|PROVINCE|DISTRICT|CITY|TEL:|'
        r'\bRD\b|\bST\b|\bAVE\b|SUITE|FLOOR|LEVEL|BUILDING|BLDG|ZONE|'
        r'SUBURB|PLOT|KAWASAN|JALAN|KEJI|YUHANG|LONGGANG|BANTIAN|LO-WU|'
        r'SHEFFIELD|NAPIER|WILDWOOD|MALACKY|SHENZHEN|GUANGDONG|POST\b|ZIP|PIN\b|'
        r'IRRUNGATTUKOTTAI|SRIPERUMBUDUR|TAMIL NADU|SWITZERLAND|GERMANY|FRANCE|ITALY|SPAIN|EUROPE|UK|UNITED KINGDOM|'
        r'STREET|ROAD|AVENUE|BOULEVARD|P\.O\.\s*BOX|PO\s*BOX|P\.O\.'
    )
    
    for i, line in enumerate(header_lines[:15] + footer_lines):
        # AI Fuzzy Logic: Check for geographic landmarks
        if re.search(geo_keywords, line, re.I):
            if re.search(r'(vessel|voyage|consignment|declaration|must be|page\s*\d|unacceptable)', line, re.I):
                continue
            
            # Combine subsequent lines that look like rest of address (city, state, country, postcode)
            addr_res = line.strip()
            combined_lines = header_lines[:15] + footer_lines
            try:
                # Try to grab up to 2 more lines that look like address continuation
                for k in range(1, 3):
                    if i + k < len(combined_lines):
                        next_line = combined_lines[i + k]
                        # Accept if it looks like city/postcode/country (short, no keywords)
                        if (
                            len(next_line) <= 60
                            and not re.search(r'(vessel|voyage|consignment|declaration|must be|Tel:|Phone|Website|CIN)', next_line, re.I)
                            and re.search(r'(\d{4,6}|NEW ZEALAND|AUSTRALIA|INDIA|CHINA|USA|MALAYSIA|THAILAND|VIETNAM|SINGAPORE|INDONESIA)', next_line, re.I)
                        ):
                            addr_res += ", " + next_line.strip()
                        else:
                            break
                
                # Strip common trailing boilerplate from address
                addr_res = re.split(r'(?:CIN\s*NO|Phone|Tel|Website|Email|DECEMBER|Vessel|Voyage|Consignment|Declaration|Unacceptable)', addr_res, flags=re.I)[0].strip()
                # Also strip raw consignment refs if they accidentally got attached (e.g. XMN26SE01057)
                addr_res = re.sub(r',\s*[A-Z]{2,5}\d{2}[A-Z]{2}\d{4,8}.*', '', addr_res).strip()
                addr_res = addr_res.rstrip(",. ")
                # Check for bad extraction (e.g. random question text)
                if len(addr_res) > 100 or re.search(r'(applicable to|timber packaging|treatment|ispm)', addr_res, re.I):
                    continue
            except:
                pass
            return addr_res, False

    # Priority 2: Generic address patterns within header and footer
    phys_pat = re.search(
        r"\d{1,8}\s+[\w\s]{2,40}"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Place|Pl|Court|Ct|Avenue|Rd\.|St\.)[^\n]*",
        header + " \n " + footer, re.IGNORECASE,
    )
    if phys_pat:
        return phys_pat.group(0).strip(), False

    po_box_pat = re.search(r"P\.?\s*O\.?\s*Box\s+[\d\w]+[^\n]*", header, re.IGNORECASE)
    if po_box_pat:
        return po_box_pat.group(0).strip(), True

    return None, False


def extract_vessel(text: str) -> str | None:
    m = re.search(
        r"(?:Vessel\s*(?:name)?|MV|M/V|Ship)\s*[\:\-\_\.]*\s*([A-Za-z][\w\s\-\.]{2,50?})"
        r"(?=\s*(?:Voyage|Voy|\t|Voyage\s*number|$))",
        text, re.IGNORECASE | re.MULTILINE
    )
    if m:
        raw = _clean_vessel(m.group(1))
        if raw:
            return raw

    m = re.search(r"(?:Vessel|Ship|MV|M/V)[\s\:\-\_\.]+(?![Nn]ame)?([A-Z][^\n\t]{2,60})", text, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"^name[\s\:\_\-\.…]+", "", raw, flags=re.IGNORECASE).strip()
        raw = re.split(r"\s+Voyage|\s+[Vv]oy\.?\s+|\t|Voyage\s*number", raw, flags=re.I)[0].strip()
        raw = _clean_vessel(raw)
        if raw:
            return raw
    return None


def _clean_vessel(raw: str) -> str | None:
    # Remove leading noise
    raw = re.sub(r"^[\.…\-\s]+", "", raw).strip()
    # Remove bleeding label fragments
    raw = re.split(r"\s+Voyage|\s*Voyage\s*number", raw, flags=re.I)[0].strip()
    raw = raw.rstrip("._-:;,()[]{}").strip()
    if not raw or len(raw) < 3:
        return None
    if re.search(r'^(Voyage|Voy|Consignment|number|identifier)$', raw, re.I):
        return None
    punct_ratio = sum(1 for c in raw if c in "._-:;,()[]{}") / max(len(raw), 1)
    if punct_ratio > 0.4:
        return None
    return raw


def extract_voyage(text: str) -> str | None:
    # Anchor on Voyage number label; catch alpha-numeric sequences like 'E059' or 'E 059'
    m = re.search(r"(?:Voyage|Voy)[\.\#\:\s\-\_number]*([A-Z]{0,3}\s*[0-9]{2,10})", text, re.IGNORECASE)
    if m:
        raw = m.group(1).replace(" ", "").strip()
        if re.search(r'^(Consignment|identifier|link)$', raw, re.I):
            return None
        return raw
    
    # Fallback to older simple pattern
    m = re.search(r"(?:Voyage|Voy)[\.\#\:\s\-\_number]*([A-Z0-9\-]{2,20})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def extract_consignment_link(text: str) -> tuple[str | None, str | None]:
    """Returns (link_value, link_type). Strips any label prefix from the match."""
    patterns = [
        # Container: ABCD1234567 optionally separated with / for multiple
        (r"\b([A-Z]{4}[\s\-]?\d{7,12}(?:\s*/\s*[A-Z]{4}[\s\-]?\d{7,12})*)\b", "container"),
        (r"(?:B/?L|Bill\s+of\s+Lading)[\s\:\#\-]+([A-Z0-9\-]{5,30})", "bl"),
        (r"(?:Invoice|INV)[\s\:\#\-]+([A-Z0-9\-\/]{4,30})", "invoice"),
        (r"(?:Packing\s+List|PKL|P/?L)[\s\:\#\-]+([A-Z0-9\-\/]{4,30})", "packing_list"),
        (r"(?:Lot)[\s\:\#\-]+([A-Z0-9\-\/]{3,20})", "lot"),
    ]
    # First search near the 'Consignment' label specifically
    cons_match = re.search(
        r"(?:Consignment.{0,20}link|numerical\s+link)[\s\:\-\_\.]+([\_ A-Z0-9][\_ A-Z0-9\s\/\-\,]{4,120})",
        text, re.IGNORECASE
    )
    if cons_match:
        raw = cons_match.group(1).strip().split('\n')[0].strip()
        # Capture ALL container refs on the line (e.g. CMAU2895229, BMOU1140400, FCIU3840231)
        all_refs = re.findall(r'[A-Z]{4}[\s\-]?\d{7,12}', raw)
        if all_refs:
            return ', '.join(ref.strip() for ref in all_refs), "consignment"
        # Fallback: strip label text — keep only the first token that has a digit
        tokens = re.split(r'[\s\t]+', raw)
        for tok in tokens:
            if re.search(r'\d', tok) and len(tok) >= 5:
                return tok.strip(), "consignment"
        if raw and len(raw) > 4 and re.search(r'\d', raw):
            return raw, "consignment"
    for pat, ltype in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            # Also try to capture multiple container refs if pattern matches container type
            if ltype == "container":
                all_refs = re.findall(r'[A-Z]{4}[\s\-]?\d{7,12}', text[:600])
                if len(all_refs) > 1:
                    return ', '.join(ref.strip() for ref in all_refs), ltype
            return m.group(1).strip(), ltype
    return None, None


def extract_party(text: str, label: str) -> str | None:
    m = re.search(
        rf"{label}[\s\:\'s]+(?:name)?[\s\:]*([A-Za-z][^\n]{{3,80}})",
        text, re.IGNORECASE
    )
    if not m:
        return None
    raw = m.group(1).strip()
    raw = re.split(
        r'\s+(?:UNACCEPTABLE|TIMBER|BAMBOO|TREATMENT|CLEANLINESS|Q1|Q2|Q3|Q4|STATEMENT|PACKING)',
        raw, flags=re.I, maxsplit=1
    )[0].strip()
    raw = re.split(r'\n|\(|\)|\[|\]', raw)[0].strip()
    raw = raw.rstrip("._-:;, ")
    return raw if len(raw) >= 2 else None


def extract_date(text: str) -> tuple[str | None, bool]:
    patterns = [
        # Explicit label patterns — handle underscore/noise and permissive connectors
        (r"(?:Date[d\s]*(?:of|on|at|for)?\s*issue[d]?|Issue\s+date|Date)[:\s_]+(\d{1,2}[\/\-\.\s]{1,3}\d{1,2}[\/\-\.\s]{1,3}\d{1,4})", "%d/%m/%Y"),
        (r"(?:Date[d\s]*(?:of|on|at|for)?\s*issue[d]?|Issue\s+date|Date)[:\s_]+(\d{4}[\/\-\.\s]{1,3}\d{1,2}[\/\-\.\s]{1,3}\d{1,2})", "%Y/%m/%d"),
        # Textual Dates (e.g. 11 Dec 2025 or December 11, 2025)
        (r"(?:Date[d\s]*(?:of|on|at|for)?\s*issue[d]?|Issue\s+date|Date)[:\s_]*(\d{1,2}[\s\.\-]*[A-Za-z]{3,10}[\s\.\-]*\d{2,4})", "TEXT_DATE"),
        (r"(?:Date[d\s]*(?:of|on|at|for)?\s*issue[d]?|Issue\s+date|Date)[:\s_]*([A-Za-z]{3,10}[\s\.\-]*\d{1,2}[\s\.,\-]*\d{2,4})", "TEXT_DATE_US"),
        # Dates merged by OCR like "13202-2026" standing for 13/02-2026
        (r"(?:Date[d\s]*(?:of|on|at|for)?\s*issue[d]?|Issue\s+date|Date)[:\s_]+(\d{2})2?0?(\d{2})[\-\/](\d{4})", "%d/%m/%Y"),
        # Dates with spaces around separators (OCR artefact: "4/ 4/ 2b", where 2b is 2026)
        (r"\b(\d{1,2}[\s\/\-\.]{1,3}\d{1,2}[\s\/\-\.]{1,3}[A-Z\d]{1,4})\b", "%d/%m/%Y"),
        # Bare dates
        (r"\b(\d{4}[\-\/]\d{2}[\-\/]\d{2})\b", "%Y/%m/%d"),
        (r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", "%d/%m/%Y"),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            # Normalise separators and clean OCR noise (like 2b as 26)
            if "_" not in raw and len(m.groups()) == 3 and not re.search(r'[\/\-\.\s]', raw):
                # We matched the fused date (group 1, 2, 3)
                raw = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
            
            raw = re.sub(r'[\s\/\-\.]+', '/', raw).replace("_", "").strip().upper()
            raw = raw.replace("2B", "26") # Specific "2b" handwritten OCR artifact
            
            # Handle 2 digit years: "10/4/26" -> "10/4/2026"
            parts = raw.split("/")
            if len(parts) == 3 and len(parts[2]) == 2:
                year = int(parts[2])
                parts[2] = f"20{year:02}"
                raw = "/".join(parts)

            # Handle textual months (e.g. "12 April 2026")
            if re.search(r'[A-Za-z]{3,}', raw):
                month_names = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", 
                               "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
                words = re.findall(r'[A-Z]{3,}', raw.upper())
                for w in words:
                    # AI Fuzzy Month Correction
                    best_match, score = process.extractOne(w, month_names)
                    if score > 75:
                        raw = raw.upper().replace(w, best_match)
                        break

            for f in [fmt, "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%d %B %Y", "%d %b %Y"]:
                try:
                    d = datetime.strptime(raw, f).date()
                    today = date.today()
                    # Acceptance window: 10 years past, 5 years future
                    is_valid = d.year > (today.year - 10) and d.year < (today.year + 5)
                    return d.isoformat(), is_valid
                except ValueError:
                    continue
    return None, False


def extract_printed_name(text: str) -> str | None:
    patterns = [
        r"(?:P?rint(?:ed)?\s+name)[\:\s\_]+([A-Za-z\u4e00-\u9fff][\w\s\.]{1,50})",
        r"(?:Signed\s+by|Authorised\s+by)[\:\s\_]+([A-Z][a-zA-Z\s\.]{2,50})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            raw = re.split(r'[\(\n\_\)]', m.group(1))[0].strip()
            raw = raw.rstrip("_-. \"'")
            return raw if len(raw) >= 2 else None
    return None


def detect_letterhead(text: str, page_count: int = 1) -> bool:
    top = text[:800]
    bottom = text[-1000:] if len(text) > 1000 else ""
    check_region = top + "\n" + bottom
    
    indicators = [
        bool(re.search(r"ABN\s*:?\s*\d{2}\s*\d{3}\s*\d{3}\s*\d{3}", check_region)),
        bool(re.search(r"(?:Pty\.?\s*Ltd|Limited|Corporation|Corp\.?|Inc\.?|CO\.?\s*LTD)", check_region, re.I)),
        bool(re.search(r"\d{1,5}\s+[A-Za-z].{5,40}(?:Street|Ave|Road|Drive|Blvd|St\.|Place|Pl\.)", check_region, re.I)),
        bool(re.search(r"www\.|\.com\.au|\.com|\.cn|\.co\.nz|\.co\.uk|\.nz|@", check_region)),
        bool(re.search(r"\+61|\+64|\+44|\+1\s|\+86|\+65|\+60|\(\d{2,3}\)\s*\d{3,4}|Tel:|TEL:|Phone:", check_region, re.I)),
        bool(re.search(r"(?:INDUSTRIAL|PROVINCE|VILLAGE|TOWN|DISTRICT|ESTATE|SIPCOT|NEW ZEALAND|NAPIER|AUCKLAND|WELLINGTON)", check_region, re.I)),
        bool(re.search(r"kwetta\.com|kwetta", check_region, re.I)),
    ]
    return sum(indicators) >= 2


def detect_signature(text: str) -> tuple[bool, str | None]:
    has_digital = bool(re.search(r"(?:DocuSign|Digitally\s+signed)", text, re.I))
    has_stamp = bool(re.search(r"STAMP|SEAL|FACSIMILE|RUBBER", text, re.I))
    has_handwritten = bool(re.search(r"(?:Signature|Signed)[:\s]*[A-Z/]{0,3}[_\-xX]{3,}", text, re.I)) or \
                      bool(re.search(r"(?:Signature|Signed)[:\s][^A-Z]", text, re.I)) # looking for the label specifically
    has_printed = bool(extract_printed_name(text))
    
    if has_digital:
        return True, "docusign"
    if has_handwritten and has_stamp:
        return True, "wet+stamp"
    if has_stamp:
        return True, "stamp_only"
    if has_printed or has_handwritten:
        # Check if a name was matched right after 'Signed:'
        m = re.search(r"(?:Signature|Signed)[:\s]+([A-Z][a-zA-Z\s]{2,30})", text, re.I)
        if m:
            return True, "typed"
        return True, "handwritten"
        
    return False, None


def detect_alterations(text: str) -> tuple[bool, bool]:
    present = bool(re.search(r"(?:alteration|amendment|correction|change)[s]?", text, re.I))
    endorsed = present and bool(re.search(r"(?:endors|initial|approved|authoris)", text, re.I))
    return present, endorsed
