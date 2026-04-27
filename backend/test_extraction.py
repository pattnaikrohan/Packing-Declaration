import pytesseract, cv2, numpy as np, pdfplumber, io
from app.ingestion import dispatcher

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

files = {
    'BNE': (r'D:\Packing Declaration\Packing Declaration-BNE.pdf', 'NO', 'NO'),
    'ADL': (r'D:\Packing Declaration\PKD-ADL.pdf', 'NO', 'NO'),
    'FRE': (r'D:\Packing Declaration\PKD-FRE.pdf', 'NO', 'YES_TIMBER'),
    'MEL': (r'D:\Packing Declaration\PKD-MEL.pdf', '?', '?'),
}

for name, (f, exp_q1, exp_q2) in files.items():
    print(f'\n=== {name} ===')
    with open(f, 'rb') as fh:
        b = fh.read()
    doc = dispatcher.extract(b, f.split('\\')[-1], 'application/pdf')
    q1_ok = '✓' if doc.q1_unacceptable_material == exp_q1 else '✗'
    q2_ok = '✓' if doc.q2_timber_bamboo == exp_q2 else '✗'
    print(f'Q1: {doc.q1_unacceptable_material} {q1_ok}  (expect: {exp_q1})')
    print(f'Q2: {doc.q2_timber_bamboo} {q2_ok}  (expect: {exp_q2})')
    print(f'Q3: {doc.q3_treatment}')
    print(f'Q4: {doc.q4_cleanliness}  (expect: PRESENT)')
