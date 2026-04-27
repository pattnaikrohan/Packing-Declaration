import logging
from app.ingestion import ocr_extractor

logging.basicConfig(level=logging.INFO)

file_path = r'D:\Packing Declaration\PKD-FRE.pdf'

with open(file_path, 'rb') as f:
    file_bytes = f.read()

images = ocr_extractor._load_images_from_pdf(file_bytes)
pil_img = images[0]
gray_img, thresh_img = ocr_extractor._preprocess_image(pil_img)

text, conf, ocr_data = ocr_extractor._ocr_image(gray_img)

print("--- TEXT RESULT ---")
text_result = ocr_extractor._detect_checkboxes_from_text(text)
print(text_result)

print("\n--- CONTOUR RESULT ---")
checkbox_result = ocr_extractor._detect_checkboxes_contours(thresh_img, ocr_data)
print(checkbox_result)

print("\n--- FINAL RESOLUTION ---")
from app.ingestion.checkbox_resolver import CheckboxResolver
res = CheckboxResolver.map_resolution(
    CheckboxResolver.resolve_q1(checkbox_result["q1"], text_result["q1"]),
    CheckboxResolver.resolve_q2(checkbox_result["q2"], text_result["q2"]),
    CheckboxResolver.resolve_q3(checkbox_result["q3"], text_result["q3"]),
    CheckboxResolver.resolve_q4(checkbox_result["q4"], text_result["q4"])
)
print(res)
