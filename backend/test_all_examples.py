import os
from app.ingestion import dispatcher
import mimetypes

files = [
    r"D:\Packing Declaration\examples1\FCL Packing Declaration_2025_Annual.docx",
    r"D:\Packing Declaration\examples1\FCL_FCX Packing Declration_2025_Single.docx",
    r"D:\Packing Declaration\examples1\LCL Packing Declaration_2025_Annual.docx",
    r"D:\Packing Declaration\examples1\LCL Packing Declaration_2025_Single.docx",
    r"D:\Packing Declaration\examples1\minimum-documentary-and-import-declaration-requirements-policy-v4.2.pdf",
    r"D:\Packing Declaration\examples1\Packing declaration example - acceptable.pdf",
    r"D:\Packing Declaration\examples1\Packing-declaration-example-unacceptable.pdf",
    r"D:\Packing Declaration\examples1\packing-declaration-fact-sheet-english.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\CAN0978243 - AMPLYT0002 Packing Dec - signed.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\LCL Packing Declaration_2025_Single[0].pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\New Packing Dec(1)[0][2].docx",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Dec.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Dec[1].pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Declaration ROH2026.pdf",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Declaration.jpg",
    r"D:\Packing Declaration\RE_ Packing Declarations\Packing Declaration[2].jpg",
    r"D:\Packing Declaration\PKD-ADL.pdf",
    r"D:\Packing Declaration\PKD-FRE.pdf",
    r"D:\Packing Declaration\PKD-MEL.pdf"
]

for f in files:
    print(f"\n=== Testing: {os.path.basename(f)} ===")
    if not os.path.exists(f):
        print("  -> File not found!")
        continue
    with open(f, 'rb') as fh:
        b = fh.read()
    
    mime, _ = mimetypes.guess_type(f)
    if mime is None:
        if f.endswith('.docx'):
            mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            mime = 'application/octet-stream'

    try:
        triple_doc = dispatcher.extract(b, os.path.basename(f), mime)
        doc = triple_doc.ocr
        print(f"  Type: {doc.declaration_type}")
        print(f"  Q1: {doc.q1_unacceptable_material}")
        print(f"  Q2: {doc.q2_timber_bamboo}")
        print(f"  Q3: {doc.q3_treatment}")
        print(f"  Q4: {doc.q4_cleanliness}")
    except Exception as e:
        print(f"  ERROR: {e}")
