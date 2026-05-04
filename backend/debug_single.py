"""Quick debug: trace the exact error on a single PDF"""
import sys, os, traceback, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("POWER_AUTOMATE_URL", "")

f = Path(r"D:\Packing Declaration\RE_ Packing Declarations\CAN0978243 - AMPLYT0002 Packing Dec - signed.pdf")
data = f.read_bytes()

try:
    from app.ingestion import dispatcher
    result = dispatcher.extract(data, f.name, "application/pdf")
    print("SUCCESS")
    print(f"OCR Q1={result.ocr.q1_unacceptable_material}")
except Exception as e:
    print(f"EXCEPTION TYPE: {type(e).__name__}")
    print(f"EXCEPTION MSG:  {e}")
    traceback.print_exc()
