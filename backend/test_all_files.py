"""
Batch test script — runs ALL user-provided files through the extraction pipeline
and reports extraction quality for each.
"""
import sys, os, json, mimetypes, io
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("POWER_AUTOMATE_URL", "")  # disable PA calls for testing

from app.ingestion import dispatcher

# All files to test
FILES = [
    # Group 1: RE_ Packing Declarations
    r"D:\Packing Declaration\RE_ Packing Declarations\CAN0978243 - AMPLYT0002 Packing Dec - signed.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\LCL Packing Declaration_2025_Single[0].pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\New Packing Dec(1)[0][2].docx",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Dec.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Dec[1].pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Declaration ROH2026.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Declaration.jpg",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Declaration[2].jpg",
    # Group 2: Root level
    r"D:\Packing Declaration\Packing Declaration-BNE.pdf",
    r"D:\Packing Declaration\PKD-ADL.pdf",
    r"D:\Packing Declaration\PKD-FRE.pdf",
    r"D:\Packing Declaration\PKD-MEL.pdf",
    # Group 3: examples1
    r"D:\Packing Declaration\examples1\FCL Packing Declaration_2025_Annual.docx",
    r"D:\Packing Declaration\examples1\FCL_FCX Packing Declration_2025_Single.docx",
    r"D:\Packing Declaration\examples1\LCL Packing Declaration_2025_Annual.docx",
    r"D:\Packing Declaration\examples1\LCL Packing Declaration_2025_Single.docx",
    r"D:\Packing Declaration\examples1\minimum-documentary-and-import-declaration-requirements-policy-v4.2.pdf",
    r"D:\Packing Declaration\examples1\Packing declaration example - acceptable.pdf",
    r"D:\Packing Declaration\examples1\Packing-declaration-example-unacceptable.pdf",
    r"D:\Packing Declaration\examples1\packing-declaration-fact-sheet-english.pdf",
]

CRITICAL_FIELDS = [
    "declaration_type", "issuer_company", "vessel_name", "voyage_number",
    "consignment_ref", "date_issued", "signed", "printed_name",
    "q1_unacceptable_material", "q2_timber_bamboo", "q3_treatment", "q4_cleanliness",
    "ocr_confidence",
]

def run():
    results = []
    for fpath in FILES:
        p = Path(fpath)
        if not p.exists():
            print(f"  SKIP (not found): {p.name}")
            continue
        
        print(f"\n{'='*80}")
        print(f"  FILE: {p.name}")
        print(f"{'='*80}")
        
        file_bytes = p.read_bytes()
        mime, _ = mimetypes.guess_type(str(p))
        
        try:
            triple = dispatcher.extract(file_bytes, p.name, mime or "")
            ocr = triple.ocr
            
            filled = 0
            total = len(CRITICAL_FIELDS)
            
            print(f"  Extraction Method: {ocr.extraction_method}")
            print(f"  OCR Confidence:    {ocr.ocr_confidence:.2%}")
            print(f"  ---")
            
            for field in CRITICAL_FIELDS:
                val = getattr(ocr, field, None)
                is_filled = bool(val) and val not in ("", "NOT_FOUND", "BLANK", "ABSENT", None, "Unknown", "unknown")
                if is_filled:
                    filled += 1
                status = "[OK]" if is_filled else "[  ]"
                print(f"  {status} {field:35s} = {val}")
            
            completeness = (filled / total) * 100
            print(f"  ---")
            print(f"  COMPLETENESS: {filled}/{total} ({completeness:.0f}%)")
            
            results.append({
                "file": p.name,
                "method": ocr.extraction_method,
                "confidence": round(ocr.ocr_confidence, 4),
                "completeness": round(completeness, 1),
                "filled": filled,
                "total": total,
                "q1": ocr.q1_unacceptable_material,
                "q2": ocr.q2_timber_bamboo,
                "q3": ocr.q3_treatment,
                "q4": ocr.q4_cleanliness,
            })
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
            results.append({
                "file": p.name,
                "method": "ERROR",
                "confidence": 0,
                "completeness": 0,
                "error": str(e),
            })
    
    # Summary
    print(f"\n\n{'='*80}")
    print(f"  SUMMARY")
    print(f"{'='*80}")
    print(f"  {'File':<55} {'Method':<8} {'Conf':>6} {'Complete':>10} {'Q1':>12} {'Q2':>12} {'Q3':>12} {'Q4':>10}")
    print(f"  {'-'*55} {'-'*8} {'-'*6} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*10}")
    
    for r in results:
        if r["method"] == "ERROR":
            print(f"  {r['file']:<55} {'ERROR':<8} {r.get('error','')}")
            continue
        print(f"  {r['file']:<55} {r['method']:<8} {r['confidence']:>5.1%} {r['completeness']:>9.0f}% {r.get('q1',''):>12} {r.get('q2',''):>12} {r.get('q3',''):>12} {r.get('q4',''):>10}")
    
    # Save JSON
    out = Path(__file__).parent / "test_all_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\n  Results saved to: {out}")

if __name__ == "__main__":
    run()
