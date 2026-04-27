import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))

from app.ingestion import dispatcher, ocr_extractor
from app.ingestion.dispatcher import extract

f_path = Path(r"D:\Packing Declaration\RE_ Packing Declarations\Packing Dec.pdf")
file_bytes = f_path.read_bytes()

# Get the full text for debugging
# We'll need to reach into ocr_extractor's helper if we want coordinate data,
# but let's start with the text blocks.
from app.ingestion.ocr_extractor import extract as extract_ocr

print("\n--- RAW TEXT BLOCK ---")
# Manually run the OCR part to get the text
import pytesseract
from pdf2image import convert_from_bytes
images = convert_from_bytes(file_bytes)
tess_data = pytesseract.image_to_string(images[0])
print(tess_data)

print("\n--- DISPATCHER RESULT ---")
result = extract(file_bytes, f_path.name, "application/pdf")
print(result.model_dump_json(indent=2))
