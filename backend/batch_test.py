"""
Batch extraction test — runs all real-world PKD example files through the
full dispatcher pipeline and prints a structured report for each.

Usage (from backend/):
    python batch_test.py
"""
import sys, os, json, textwrap
sys.path.insert(0, os.path.dirname(__file__))
# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from app.ingestion import dispatcher

SAMPLES_DIR = Path(r"D:\Packing Declaration\RE_ Packing Declarations")

FILES = [
    "CAN0978243 - AMPLYT0002 Packing Dec - signed.pdf",
    "LCL Packing Declaration_2025_Single[0].pdf",
    "New Packing Dec(1)[0][2].docx",
    "Packing Dec.pdf",
    "Packing Dec[1].pdf",
    "Packing Declaration ROH2026.pdf",
    "Packing Declaration.jpg",
    "Packing Declaration[2].jpg",
]

EXT_CT = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
}

FIELDS = [
    "file_name", "extraction_method", "ocr_confidence",
    "declaration_type",
    "issuer_company", "issuer_address", "issuer_address_is_po_box",
    "vessel_name", "voyage_number", "consignment_ref",
    "exporter", "importer",
    "date_issued", "date_valid",
    "signed", "signature_type", "printed_name",
    "letterhead_present",
    "q1_unacceptable_material",
    "q2_timber_bamboo",
    "q3_treatment",
    "q4_cleanliness",
    "alterations_present", "alterations_endorsed",
]

SEP = "=" * 80

def flag(value, field):
    """Colour-code important fields in terminal output."""
    blank_fields = {"q1_unacceptable_material", "q2_timber_bamboo", "q3_treatment"}
    if field in blank_fields and value in ("BLANK", None, ""):
        return f"\033[33m{value}\033[0m"   # yellow = needs attention
    if field == "declaration_type" and value is None:
        return f"\033[33mNone\033[0m"
    if field == "issuer_company" and value is None:
        return f"\033[33mNone\033[0m"
    if field == "date_issued" and value is None:
        return f"\033[33mNone\033[0m"
    if field == "signed" and value is False:
        return f"\033[31mFalse\033[0m"    # red = unsigned
    return str(value)


results = []
errors  = []

print(f"\n{SEP}")
print("  PKD BATCH EXTRACTION TEST")
print(f"{SEP}\n")

for fname in FILES:
    path = SAMPLES_DIR / fname
    ext  = Path(fname).suffix.lower()
    ct   = EXT_CT.get(ext, "")

    print(f"[FILE] {fname}")
    print(f"    Path: {path}")

    if not path.exists():
        print(f"    \033[31m[SKIP] File not found\033[0m\n")
        errors.append({"file": fname, "error": "not found"})
        continue

    try:
        file_bytes = path.read_bytes()
        result = dispatcher.extract(file_bytes, fname, ct)
        d = result.model_dump()

        print(f"    Route : {d['extraction_method']}  |  OCR conf: {d.get('ocr_confidence', 'N/A')}")
        print()

        for f in FIELDS:
            if f in ("file_name", "extraction_method", "ocr_confidence"):
                continue
            v = d.get(f)
            print(f"    {f:<35} {flag(v, f)}")

        results.append(d)
        print()

    except Exception as e:
        import traceback
        msg = traceback.format_exc()
        print(f"    \033[31m[ERROR] {e}\033[0m")
        print(textwrap.indent(msg, "    "))
        errors.append({"file": fname, "error": str(e), "traceback": msg})

print(SEP)
print(f"  SUMMARY:  {len(results)} succeeded  |  {len(errors)} failed/skipped")
print(SEP)

if errors:
    print("\n--- FAILURES ---")
    for e in errors:
        print(f"  {e['file']}: {e['error']}")

# Dump JSON results for inspection
out_path = Path(__file__).parent / "batch_test_results.json"
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=2, default=str)

print(f"\nFull JSON results saved to: {out_path}\n")
