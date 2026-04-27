"""
OCR extractor for scanned PDFs and image files (JPEG, PNG).
Pipeline: file → image(s) at 300dpi → grayscale → adaptive threshold
         → pytesseract (word-level) → checkbox contour detection → field regex.
Gracefully degrades if Tesseract or Poppler are unavailable.
"""
import io
import logging
import re
import cv2
import numpy as np
from PIL import Image

from app.ingestion.schema import PackingDeclaration
from app.ingestion import extractors_common as ec
from app.ingestion.checkbox_resolver import CheckboxResolver
from app.config import settings

logger = logging.getLogger(__name__)


def _load_images_from_pdf(file_bytes: bytes) -> list:
    try:
        import pdfplumber
        import io
        images = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                images.append(page.to_image(resolution=300).original)
        return images
    except Exception as e:
        logger.warning(f"pdfplumber image generation failed: {e}")
        return []


def _load_image(file_bytes: bytes) -> list:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        return [img]
    except Exception as e:
        logger.warning(f"Pillow image load failed: {e}")
        return []


def _preprocess_image(pil_img) -> "tuple[np.ndarray | None, np.ndarray | None]":
    """Returns (gray, thresholded). Gray is used for OCR coords; thresholded for contours."""
    try:
        import cv2
        img_array = np.array(pil_img.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Advanced localized noise reduction for scanned documents
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        processed = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Morphological closing to mend broken characters and clear small speckles
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        opened = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel, iterations=1)
        
        return gray, opened
    except ImportError:
        logger.warning("OpenCV not available — skipping image pre-processing")
        gray = np.array(pil_img.convert("L"))
        return gray, gray
    except Exception as e:
        logger.warning(f"Image pre-processing failed: {e}")
        return None, None


def _ocr_image(cv_img) -> tuple[str, float, dict]:
    try:
        import pytesseract
        from pytesseract import Output
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        pil_img = Image.fromarray(cv_img)
        # Deep Neural Net OCR (OEM_LSTM) with uniform text block mapping (PSM 6) for stable regex layouts
        data = pytesseract.image_to_data(pil_img, lang="eng", config="--oem 3 --psm 6", output_type=Output.DICT)
        confs = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) > 0]
        mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        lines = []
        current_line = []
        prev_line_num = -1
        for j in range(len(data["text"])):
            w_text = data["text"][j].strip()
            if not w_text:
                continue
            
            line_num = data["line_num"][j]
            if prev_line_num != -1 and line_num != prev_line_num:
                lines.append(" ".join(current_line))
                current_line = []
            
            current_line.append(w_text)
            prev_line_num = line_num
        
        if current_line:
            lines.append(" ".join(current_line))
            
        text = "\n".join(lines)
        return text, mean_conf, data
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
        return "", 0.0, {}


def _detect_checkboxes_contours(cv_img, ocr_data=None) -> dict:
    """
    Finds square-ish contours, checks pixel density (tick OR X = marked),
    then maps each marked checkbox to the nearest YES/NO/treatment option label
    using OCR word X/Y coordinates for precision.
    Falls back to legacy zone slicing if OCR is unavailable.
    """
    result = {"q1": "NOT_FOUND", "q2": "NOT_FOUND", "q3": "NOT_FOUND", "q4": "NOT_FOUND"}
    try:
        import cv2
        h, w = cv_img.shape[:2]

        # Default anchors (safe legacy fallback)
        anchors = {"q1": h * 0.20, "q2": h * 0.40, "q3": h * 0.60, "q4": h * 0.85}

        # Per-question option label positions: {q_key: {option_name: [(x, y), ...]}}
        option_positions = {"q1": {}, "q2": {}, "q3": {}, "q4": {}}

        if ocr_data and "text" in ocr_data:
            q_y_vals = {"q1": [], "q2": [], "q3": [], "q4": []}

            # Pass 1: Build question Y-anchors
            for j, word in enumerate(ocr_data["text"]):
                w_text = word.strip().upper()
                if not w_text:
                    continue
                y_center = ocr_data["top"][j] + ocr_data["height"][j] / 2

                if any(k in w_text for k in ["Q1", "UNACCEPT", "PROHIBIT"]):
                    q_y_vals["q1"].append(y_center)
                elif any(k in w_text for k in ["Q2", "TIMBER", "BAMBOO", "DUNNAGE"]):
                    q_y_vals["q2"].append(y_center)
                elif any(k in w_text for k in ["Q3", "TREATMENT", "ISPM", "DAFF", "CERTIFIED"]):
                    q_y_vals["q3"].append(y_center)
                elif any(k in w_text for k in ["Q4", "CLEANLINESS", "CLEAN"]):
                    q_y_vals["q4"].append(y_center)

            for q_key in ["q1", "q2", "q3", "q4"]:
                if q_y_vals[q_key]:
                    anchors[q_key] = sum(q_y_vals[q_key]) / len(q_y_vals[q_key])

            # Pass 2: Map YES/NO/treatment option labels to their questions
            for j, word in enumerate(ocr_data["text"]):
                w_text = word.strip().upper()
                if not w_text:
                    continue
                y_center = ocr_data["top"][j] + ocr_data["height"][j] / 2
                x_center = ocr_data["left"][j] + ocr_data["width"][j] / 2

                # Assign word to nearest question (within 18% vertical band)
                closest_q = min(anchors.keys(), key=lambda k: abs(anchors[k] - y_center))
                if abs(anchors[closest_q] - y_center) > h * 0.18:
                    continue

                # Tighten: Only accept as label if it's a short token (likely the box label)
                # and not part of a long question sentence.
                # Word data 'level' 5 is a word.
                label_candidates_yes = ["YES", "Y", "V", "TRUE", "CHECKED"]
                label_candidates_no = ["NO", "N", "NIL", "NONE", "FALSE", "NA", "N/A"]
                
                if any(re.search(rf'^{k}$', w_text, re.I) for k in label_candidates_yes):
                    # Basic filter: ignore if it looks like it's part of the question text
                    # (very early in the line or surrounded by many words)
                    option_positions[closest_q].setdefault("YES", []).append((x_center, y_center))
                elif any(re.search(rf'^{k}$', w_text, re.I) for k in label_candidates_no):
                    option_positions[closest_q].setdefault("NO", []).append((x_center, y_center))
                elif "ISPM" in w_text:
                    option_positions[closest_q].setdefault("ISPM15", []).append((x_center, y_center))
                elif "DAFF" in w_text or "CERTIF" in w_text:
                    option_positions[closest_q].setdefault("DAFF_CERTIFIED", []).append((x_center, y_center))
                elif w_text in ("TREATED",) and "NOT" in (ocr_data["text"][j-1] if j > 0 else ""):
                    option_positions[closest_q].setdefault("NOT_TREATED", []).append((x_center, y_center))

        # --- MORPHOLOGICAL BOX ISOLATION ---
        # 1. Invert image so ink is white (255) and background is black (0)
        inverted = cv2.bitwise_not(cv_img) if cv_img.dtype == np.uint8 else cv_img
        
        # 2. Extract horizontal and vertical lines to isolate pure rectangles
        kernel_length = max(12, int(w / 150))
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_length, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_length))
        
        lines_h = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel_h)
        lines_v = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel_v)
        
        # 3. Combine to reconstruct only the boxes (erasing diagonal checkmarks)
        boxes_img = cv2.bitwise_or(lines_h, lines_v)
        
        # 4. Small close to connect broken box corners
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        boxes_img = cv2.morphologyEx(boxes_img, cv2.MORPH_CLOSE, kernel_close)

        # Detect checkbox contours on the cleaned boxes_img!
        contours, _ = cv2.findContours(
            boxes_img,
            cv2.RETR_EXTERNAL,   # EXTERNAL only — avoids sub-contours inside characters
            cv2.CHAIN_APPROX_SIMPLE,
        )
        candidates = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            # Relaxed bounds to allow slightly distorted boxes from the morphology
            if cw < 15 or ch < 15 or cw > 200 or ch > 200:
                continue
            if 0.50 <= (cw / ch) <= 2.0:
                # OMR Optimization: Crop the inner 25% from the ORIGINAL inverted image
                # to check for the tick mark (since the tick mark was erased from boxes_img)
                margin_x = int(cw * 0.25)
                margin_y = int(ch * 0.25)
                inner_crop = inverted[y + margin_y : y + ch - margin_y, x + margin_x : x + cw - margin_x]
                
                if inner_crop.size == 0:
                    continue
                    
                # Calculate ink density strictly on the inside of the original box
                density = np.count_nonzero(inner_crop) / inner_crop.size
                candidates.append({
                    "x": x + cw / 2,
                    "y": y + ch / 2,
                    "density": density,
                    "ticked": False, # Will be determined relatively
                })

        # RELATIVE DENSITY STRATEGY:
        # Group all valid boxes line-by-line (by closest question).
        # The box with the highest density is the ticked one, assuming it passes a lower nominal threshold.
        q_groups = {"q1": [], "q2": [], "q3": [], "q4": []}
        for c in candidates:
            closest_q = min(anchors.keys(), key=lambda k: abs(anchors[k] - c["y"]))
            q_groups[closest_q].append(c)

        for q, cands in q_groups.items():
            if not cands: continue
            max_cand = max(cands, key=lambda c: c["density"])
            # With borders removed, an empty box is ~0.0 density. 
            # A tick/cross easily hits > 0.05.
            if max_cand["density"] > 0.05:
                max_cand["ticked"] = True

        for c in candidates:
            if not c["ticked"]:
                continue

            closest_q = min(anchors.keys(), key=lambda k: abs(anchors[k] - c["y"]))
            q_candidates = [cand for cand in candidates if min(anchors.keys(), key=lambda k: abs(anchors[k] - cand["y"])) == closest_q]
            q_candidates.sort(key=lambda cand: cand["x"])
            
            opts = option_positions.get(closest_q, {})

            if opts:
                # DEEP OPTIMIZATION: Map by relative horizontal order for Q1/Q2/Q4
                # Group all found option labels for this question by X coordinate
                flat_opts = []
                for name, pos_list in opts.items():
                    for ox, oy in pos_list:
                        flat_opts.append({"name": name, "x": ox})
                flat_opts.sort(key=lambda o: o["x"])

                # Relative Order Strategy: 
                # If we have a sequence of boxes and a sequence of labels on one line, 
                # they almost certainly map 1:1 in order.
                if len(q_candidates) >= 2:
                    # AI INFERENCE: If we find 2 boxes but only 1 label (e.g. YES), 
                    # infer the 2nd is NO based on sequence.
                    labels_to_map = flat_opts
                    if len(flat_opts) == 1 and closest_q in ("q1", "q4"):
                        # Inferred 1:1 mapping for simple YES/NO questions
                        if flat_opts[0]["name"] == "YES":
                            labels_to_map.append({"name": "NO", "x": 9999})
                        else:
                            labels_to_map.insert(0, {"name": "YES", "x": -9999})
                    
                    if len(labels_to_map) >= 2:
                        try:
                            c_idx = next(i for i, cand in enumerate(q_candidates) if cand == c)
                            if c_idx < len(labels_to_map):
                                _apply_checkbox(result, closest_q, labels_to_map[c_idx]["name"])
                                continue
                        except StopIteration:
                            pass

                # Fallback: Find the nearest option label by horizontal (X) distance
                best_option = None
                best_dist = float("inf")
                for opt_name, positions in opts.items():
                    for ox, oy in positions:
                        dist = abs(ox - c["x"])
                        if dist < best_dist:
                            best_dist = dist
                            best_option = opt_name

                # Accept if label is within 20% of page width
                if best_option and best_dist < w * 0.20:
                    _apply_checkbox(result, closest_q, best_option)
                    continue

            # Geometrical fallback: if label mapping failed
            if closest_q in ("q1", "q4"):
                ordered = sorted(q_candidates, key=lambda cb: cb["x"])
                if len(ordered) == 2:
                    is_right = (ordered[1]["x"] == c["x"] and ordered[1]["y"] == c["y"])
                    _apply_checkbox(result, closest_q, "NO" if is_right else "YES")
                    continue
                elif len(ordered) >= 1:
                    # Pick left/right half of the page based on the CHECKBOX center, not word center
                    _apply_checkbox(result, closest_q, "NO" if c["x"] > w * 0.45 else "YES")
                    continue

            # Fallback: no option labels found — default to YES/PRESENT for marked boxes
            _apply_checkbox_default(result, closest_q)

    except Exception as e:
        logger.warning(f"Contour checkbox detection failed: {e}")
        
    # Standardize result: If it's still specifically NOT_FOUND after checking for ticked boxes,
    # it means we at least looked but found nothing ticked. If the boxes themselves exist 
    # but aren't ticked, we should label as DECLARED_BLANK.
    # To do this robustly, we'd check against our candidates' locations.
    for q in ["q1", "q2", "q3", "q4"]:
        if result[q] == "NOT_FOUND":
            # If we found at least one box for this question but none were ticked
            if anchors.get(q) and any(min(anchors.keys(), key=lambda k: abs(anchors[k] - cand["y"])) == q for cand in candidates):
                result[q] = "DECLARED_BLANK"
                
    return result


def _apply_checkbox(result: dict, q: str, option: str) -> None:
    """Apply a specifically identified option to the result dict."""
    if q == "q1":
        result["q1"] = "YES" if option == "YES" else "NO"
    elif q == "q2":
        if option == "YES":
            result["q2"] = "YES_TIMBER"
        elif option == "NO":
            result["q2"] = "NO"
    elif q == "q3":
        mapping = {
            "ISPM15": "ISPM15",
            "DAFF_CERTIFIED": "DAFF_CERTIFIED",
            "NOT_TREATED": "NOT_TREATED",
            "NO": "NOT_APPLICABLE",
        }
        if option in mapping and result["q3"] == "BLANK":
            result["q3"] = mapping[option]
    elif q == "q4":
        result["q4"] = "PRESENT"


def _apply_checkbox_default(result: dict, q: str) -> None:
    """Fallback: a ticked box with no nearby label defaults conservatively."""
    if q == "q1" and result["q1"] == "NOT_FOUND":
        result["q1"] = "YES"
    elif q == "q2" and result["q2"] == "NOT_FOUND":
        result["q2"] = "YES_TIMBER"
    elif q == "q3" and result["q3"] == "NOT_FOUND":
        result["q3"] = "ISPM15"
    elif q == "q4":
        result["q4"] = "PRESENT"


def _detect_checkboxes_from_text(text: str) -> dict:
    """
    Reads OCR text patterns between option labels to detect which checkbox is marked.

    OCR consistently represents empty checkboxes as bracket-like characters: LJ, L], [J, C], |_|
    Ticked/X'd checkboxes appear as: missing (merged with text), or non-bracket chars (Mi, La, M, V, X...)

    Uses 3 progressively more permissive strategies per question so layout changes are covered:
      1. Anchored: looks for "A1 / A2" answer-label prefix
      2. Keyword: looks for YES/NO/Timber/Bamboo keywords in the Q-section text region
      3. Fallback: contour result (handled in caller)
    """
    import re
    result = {"q1": None, "q2": None, "q3": None, "q4": None}

    # ── Helper: empty vs marked ──────────────────────────────────────────────
    # OCR empty box chars: square-bracket-like sequences
    EMPTY_BOX_RE = re.compile(r'^[\s\[\]|LlCcJj_\{\}°\u25a1\u2610Oo01]{0,8}$')

    def is_empty_box(s: str) -> bool:
        return bool(EMPTY_BOX_RE.match(s.strip()))

    def is_mark(s: str) -> bool:
        s = s.strip()
        # If OCR returns a single char like 'X', 'V', '*', it's a mark.
        if len(s) == 1 and s.upper() in "XV*":
            return True
        if not s:
            return True   # nothing between options = mark consumed/merged = ticked
        return not is_empty_box(s)

    # ── Extract Q-section boundaries ─────────────────────────────────────────
    tu = text.upper()
    q1_start = next((tu.find(k) for k in ["Q1", "A1 ", "UNACCEPTABLE PACK", "PROHIBITED"] if k in tu), 0)
    q2_start = next((tu.find(k) for k in ["Q2", "A2 ", "TIMBER/BAMBOO", "TIMBER BAMBOO"] if k in tu), -1)
    q3_start = next((tu.find(k) for k in ["Q3", "A3 ", "TREATMENT CERT", "ISPM 15"] if k in tu), -1)
    q4_start = next((tu.find(k) for k in ["Q4", "A4 ", "CLEANLINESS", "CONTAINER"] if k in tu), -1)

    def section(start, end_next):
        if start < 0:
            return ""
        end = end_next if end_next > start else len(text)
        return text[start:end]

    q1_text = section(q1_start, q2_start)
    q2_text = section(q2_start, q3_start)
    q3_text = section(q3_start, q4_start)

    # ── Q1 ───────────────────────────────────────────────────────────────────
    # Strategy 1: A1 label present
    m = re.search(
        r"A1[\s\.\,]{0,5}(.{0,10})\s*YES\s*(.{0,10})\s*NO\s*(.{0,10})",
        q1_text, re.IGNORECASE
    )
    if m:
        before_yes, between, after_no = m.group(1), m.group(2), m.group(3)
        if is_mark(after_no) and is_empty_box(between):
            result["q1"] = "NO"
        elif is_mark(between):
            # AI Refinement: If there's a mark between YES and NO,
            # check if it's closer to YES or NO.
            # If "between" starts with a lot of space/empty box char, it's probably for NO.
            stripped = between.lstrip()
            if len(between) > 4 and (len(between) - len(stripped)) > 4:
                result["q1"] = "NO"
            else:
                result["q1"] = "YES"
        elif is_mark(before_yes):
            result["q1"] = "YES"

    # Strategy 2: Just YES … NO in Q1 region (no A1 label required)
    if result["q1"] is None and q1_text:
        # Match pattern: [SOMETHING/MARK] [LABEL OPTIONAL] NO [MARK]
        m = re.search(r"(?:YES(?:[\s\.\,]*|)|ws\s*[OoI1l]{1,2}|Ol|v\s+|[\*\xde])\s*(.{0,20})\s*NO\b\s*(.{0,15})", q1_text, re.IGNORECASE)
        if m:
            between, after_no = m.group(1), m.group(2)
            # Stop "after_no" at next line break to avoid spilling into Q2
            after_no = re.split(r"[\n\r]", after_no)[0]
            if is_mark(after_no) and is_empty_box(between):
                result["q1"] = "NO"
            elif is_mark(between):
                # Proximity check for the shared gap
                stripped = between.lstrip()
                if len(between) > 6 and (len(between) - len(stripped)) > 4:
                    result["q1"] = "NO"
                else:
                    result["q1"] = "YES"

    # ── Q2 ───────────────────────────────────────────────────────────────────
    # Strategy 1: Three-option row — YES Timber / YES Bamboo / NO
    m = re.search(
        r"(?:A2[\s\.\,~\-]{0,8}.{0,10})?"           # optional A2 label
        r"(?:YES\s+)?TIMBER\s*(.{0,12})\s*"          # after TIMBER option
        r"(?:YES\s+)?BAMBOO\s*(.{0,12})\s*"          # after BAMBOO option
        r"NO\s*(.{0,15})",                            # after NO option
        q2_text, re.IGNORECASE
    )
    if m:
        after_timber = m.group(1)
        after_bamboo = m.group(2)
        after_no     = re.split(r"[\n\r(]", m.group(3))[0]   # stop at newline or '('

        if is_mark(after_no) and is_empty_box(after_timber) and is_empty_box(after_bamboo):
            result["q2"] = "NO"
        elif is_mark(after_timber):
            result["q2"] = "YES_TIMBER"
        elif is_mark(after_bamboo):
            result["q2"] = "YES_BAMBOO"
        elif is_empty_box(after_timber) and after_timber.strip() == "":
            # Nothing between TIMBER and BAMBOO = ticked box merged → YES_TIMBER
            result["q2"] = "YES_TIMBER"

    # Strategy 2: Two-option row — YES / NO (some layouts only say YES/NO not YES Timber)
    if result["q2"] is None and q2_text:
        m = re.search(r"YES\s*(.{0,10})\s*NO\s*(.{0,15})", q2_text, re.IGNORECASE)
        if m:
            between, after_no = m.group(1), re.split(r"[\n\r(]", m.group(2))[0]
            if is_mark(after_no) and is_empty_box(between):
                result["q2"] = "NO"
            elif is_mark(between):
                result["q2"] = "YES_TIMBER"

    # ── Q3 ───────────────────────────────────────────────────────────────────
    # Text-based Q3: check if ISPM15 or DAFF appears ticked
    if q3_text:
        # ISPM15 checked = mark between Q3 start and "ISPM" keyword, or directly after
        ispm_m = re.search(r"ISPM[\s\-]*15\s*(.{0,12})", q3_text, re.IGNORECASE)
        daff_m = re.search(r"DAFF.{0,20}CERTIF\s*(.{0,12})", q3_text, re.IGNORECASE)
        nt_m   = re.search(r"NOT\s+TREATED\s*(.{0,12})", q3_text, re.IGNORECASE)
        if ispm_m and is_mark(ispm_m.group(1)):
            result["q3"] = "ISPM15"
        elif daff_m and is_mark(daff_m.group(1)):
            result["q3"] = "DAFF_CERTIFIED"
        elif nt_m and is_mark(nt_m.group(1)):
            result["q3"] = "NOT_TREATED"

    return result




def extract(file_bytes: bytes, is_pdf: bool = False) -> PackingDeclaration:
    images = _load_images_from_pdf(file_bytes) if is_pdf else _load_image(file_bytes)

    if not images:
        logger.warning("OCR: no images produced — returning blank extraction")
        return PackingDeclaration(extraction_method="ocr", ocr_confidence=0.0)

    all_text = []
    total_conf = []
    checkbox_result = {"q1": "BLANK", "q2": "BLANK", "q3": "BLANK", "q4": "ABSENT"}

    for i, pil_img in enumerate(images):
        gray_img, thresh_img = _preprocess_image(pil_img)
        if thresh_img is None:
            continue
        # Use grayscale for OCR text + word coordinates (better readability)
        text, conf, ocr_data = _ocr_image(gray_img)
        all_text.append(text)
        total_conf.append(conf)
        if i == 0:
            # Use thresholded image for contour detection (clean edges)
            checkbox_result = _detect_checkboxes_contours(thresh_img, ocr_data)

    full_text = "\n".join(all_text)
    mean_confidence = sum(total_conf) / len(total_conf) if total_conf else 0.0

    text_result = _detect_checkboxes_from_text(full_text)

    # Cascading Hierarchical Resolution
    res = CheckboxResolver.map_resolution(
        CheckboxResolver.resolve_q1(checkbox_result["q1"], text_result["q1"]),
        CheckboxResolver.resolve_q2(checkbox_result["q2"], text_result["q2"]),
        CheckboxResolver.resolve_q3(checkbox_result["q3"], text_result["q3"]),
        CheckboxResolver.resolve_q4(checkbox_result["q4"], text_result["q4"])
    )

    logger.info(
        "[compliance] Checkbox Resolution — text:%s visual:%s resolved:%s",
        text_result, checkbox_result, res
    )



    # ── Token & BBox Generation (for LayoutLMv3) ──
    tokens = []
    bboxes = []
    page_size = [images[0].size[0], images[0].size[1]] if images else [0, 0]

    for pil_img in images:
        gray_img, _ = _preprocess_image(pil_img)
        if gray_img is None: continue
        _, _, data = _ocr_image(gray_img)
        w_img, h_img = pil_img.size
        
        for j in range(len(data["text"])):
            txt = data["text"][j].strip()
            if not txt: continue
            
            # Normalize to 0-1000 for standard Transformer inputs
            x1 = int((data["left"][j] / w_img) * 1000)
            y1 = int((data["top"][j] / h_img) * 1000)
            x2 = int(((data["left"][j] + data["width"][j]) / w_img) * 1000)
            y2 = int(((data["top"][j] + data["height"][j]) / h_img) * 1000)
            
            tokens.append(txt)
            bboxes.append([x1, y1, x2, y2])

    # ── Heuristic Extraction (Deterministic Fallback) ──
    addr, is_po = ec.extract_address(full_text)
    consignment, _ = ec.extract_consignment_link(full_text)
    date_str, date_valid = ec.extract_date(full_text)
    signed, sig_type = ec.detect_signature(full_text)
    alterations, endorsed = ec.detect_alterations(full_text)

    result = PackingDeclaration(
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
        q1_unacceptable_material=res["q1"],
        q2_timber_bamboo=res["q2"],
        q3_treatment=res["q3"],
        q4_cleanliness=res["q4"],
        alterations_present=alterations,
        alterations_endorsed=endorsed,
        extraction_method="ocr",
        ocr_confidence=round(mean_confidence, 4),
        field_scores={
            "issuer_company": round(mean_confidence * 0.95, 2),
            "issuer_address": round(mean_confidence * 0.92, 2),
            "vessel_name": round(mean_confidence * 0.9, 2),
            "voyage_number": round(mean_confidence * 0.9, 2),
            "consignment_ref": round(1.0 if consignment else 0.0, 2),
            "date_issued": round(0.95 if date_str else 0.0, 2),
            "signed": round(0.98 if signed else 0.0, 2),
            "printed_name": round(mean_confidence * 0.85, 2),
            "q1": 0.99 if res["q1"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
            "q2": 0.99 if res["q2"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
            "q3": 0.99 if res["q3"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
            "q4": 0.99 if res["q4"] not in ("NOT_FOUND", "DECLARED_BLANK") else 0.5,
        }
    )

    # Attach raw layout data for ML layer
    result._tokens = tokens
    result._bboxes = bboxes
    result._page_size = page_size
    result._raw_text = full_text

    return result


def extract_roi(file_bytes: bytes, x1: float, y1: float, x2: float, y2: float, is_pdf: bool = False) -> str:
    """
    Extracts text from a specific region (coordinates are 0.0 - 1.0 relative to page size).
    """
    images = _load_images_from_pdf(file_bytes) if is_pdf else _load_image(file_bytes)
    if not images:
        return ""
    
    # Process the first page (PKDs are usually single-page for info points)
    img = images[0]
    w, h = img.size
    
    # Convert relative to pixel coordinates
    left = int(x1 * w)
    top = int(y1 * h)
    right = int(x2 * w)
    bottom = int(y2 * h)
    
    # Safety crop
    left, top = max(0, left), max(0, top)
    right, bottom = min(w, right), min(h, bottom)
    
    if right <= left or bottom <= top:
        return ""
        
    roi = img.crop((left, top, right, bottom))
    
    # OCR the ROI
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    # Higher PSM (7 or 8) is often better for single-line snippets
    text = pytesseract.image_to_string(roi, lang="eng", config="--psm 7").strip()
    
    logger.info(f"[roi] Extracted text from box ({x1:.2f},{y1:.2f} to {x2:.2f},{y2:.2f}): '{text}'")
    return text
