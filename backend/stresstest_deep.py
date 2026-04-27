import sys
import os
import json
from pathlib import Path
from typing import List

# Ensure app is in path
sys.path.insert(0, os.path.dirname(__file__))

from app.ingestion import dispatcher

SEARCH_DIRS = [
    r"D:\Packing Declaration\examples2",
    r"D:\Packing Declaration\Packing declaration examples",
    r"D:\Packing Declaration\RE_ Packing Declarations",
    r"D:\Packing Declaration" # Also check root for files listed directly
]

EXT_CT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png"
}

def discover_files() -> List[Path]:
    found = []
    seen = set()
    for d in SEARCH_DIRS:
        p = Path(d)
        if not p.exists(): continue
        for item in p.iterdir():
            if item.is_file() and item.suffix.lower() in EXT_CT:
                # Use absolute path to ensure uniqueness
                abs_p = item.resolve()
                if abs_p not in seen:
                    found.append(item)
                    seen.add(abs_p)
    return found

def run_test():
    files = discover_files()
    print(f"\n{'='*100}")
    print(f"  DEEP VERIFICATION SWEEP: {len(files)} SAMPLES")
    print(f"{'='*100}\n")
    
    print(f"{'FILE NAME':<45} | {'ROUTE':<8} | {'Q1':<6} | {'DATE':<12} | {'COMPANY':<15}")
    print("-" * 100)
    
    results = []
    for f in sorted(files, key=lambda x: x.name):
        try:
            file_bytes = f.read_bytes()
            ct = EXT_CT.get(f.suffix.lower(), "application/octet-stream")
            res = dispatcher.extract(file_bytes, f.name, ct)
            d = res.model_dump()
            
            q1 = d.get('q1_unacceptable_material', 'BLANK')
            date = d.get('date_issued') or 'null'
            company = d.get('issuer_company') or 'null'
            route = d.get('extraction_method', '???')
            
            # Truncate company for table
            company_disp = (company[:13] + '..') if len(str(company)) > 15 else str(company)
            
            print(f"{f.name[:45]:<45} | {route:<8} | {q1:<6} | {date:<12} | {company_disp:<15}")
            
            results.append({
                "file": f.name,
                "path": str(f),
                "result": d
            })
        except Exception as e:
            print(f"{f.name[:45]:<45} | ERROR    | {str(e)[:40]}")

    print(f"\n{'='*100}")
    print(f"  SWEEP COMPLETE. Full log saved to stresstest_results.json")
    print(f"{'='*100}\n")
    
    with open("stresstest_results.json", "w", encoding="utf-8") as out:
        json.dump(results, out, indent=2, default=str)

if __name__ == "__main__":
    run_test()
