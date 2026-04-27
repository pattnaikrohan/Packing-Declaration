import cv2
import numpy as np
from app.ingestion import ocr_extractor
from app.ingestion.extractors_common import *

def debug_fre():
    file_path = r'D:\Packing Declaration\PKD-FRE.pdf'
    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    images = ocr_extractor._load_images_from_pdf(file_bytes)
    pil_img = images[0]
    gray, thresh = ocr_extractor._preprocess_image(pil_img)
    text, conf, data = ocr_extractor._ocr_image(gray)

    print("--- COMPANY EXTRACTION ---")
    print(f"Extraction result: {extract_company(text)}")
    
    print("\n--- ADDRESS EXTRACTION ---")
    addr, is_po = extract_address(text)
    print(f"Extraction result: {addr} (PO: {is_po})")

    print("\n--- CONSIGNMENT EXTRACTION ---")
    cons, ctype = extract_consignment_link(text)
    print(f"Extraction result: {cons} ({ctype})")

    print("\n--- Q1 DEBUG ---")
    res = {"q1": None, "q2": None, "q3": None, "q4": None}
    
    # Run contour detection logic but inspect candidates
    # We need to monkeypath or just run the logic manually here
    h, w = thresh.shape
    q_regions = ocr_extractor._get_q_regions(data, text, w, h)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if 10 < cw < 60 and 10 < ch < 60:
            aspect = cw / ch
            if 0.7 < aspect < 1.4:
                # Check pixel density
                roi = thresh[y:y+ch, x:x+cw]
                white_px = cv2.countNonZero(roi)
                total_px = cw * ch
                density = white_px / total_px
                if density > 0.15: # Threshold from ocr_extractor
                    candidates.append({"x": x, "y": y, "w": cw, "h": ch, "d": density})

    print(f"Total candidates found: {len(candidates)}")
    for q_name, region in q_regions.items():
        if q_name == 'q1':
            print(f"Checking region {q_name}: {region}")
            q_candidates = [c for c in candidates if region[0] <= c["y"] <= region[1]]
            print(f"  Candidates in region: {q_candidates}")
            if q_candidates:
                # Map them to NO/YES based on X
                ordered = sorted(q_candidates, key=lambda x: x["x"])
                for i, c in enumerate(ordered):
                    print(f"    - Candidate {i}: x={c['x']}, density={c['d']:.2f}")

    print("\n--- TEXT Q1 DEBUG ---")
    text_res = ocr_extractor._detect_checkboxes_from_text(text)
    print(f"Text result for q1: {text_res.get('q1')}")

debug_fre()
