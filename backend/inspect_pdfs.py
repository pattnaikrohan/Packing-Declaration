import pdfplumber
from io import BytesIO

files = [
    r'D:\Packing Declaration\Packing Declaration-BNE.pdf',
    r'D:\Packing Declaration\PKD-ADL.pdf',
    r'D:\Packing Declaration\PKD-FRE.pdf',
    r'D:\Packing Declaration\PKD-MEL.pdf',
]

for path in files:
    fname = path.split('\\')[-1]
    print(f'\n{"="*60}')
    print(f'FILE: {fname}')
    print('='*60)
    with open(path, 'rb') as f:
        data = f.read()
    with pdfplumber.open(BytesIO(data)) as pdf:
        print(f'Pages: {len(pdf.pages)}')
        for i, page in enumerate(pdf.pages[:2]):
            text = page.extract_text() or ''
            print(f'\n--- Page {i+1} text ({len(text)} chars) ---')
            print(text[:2000])
            annots = page.annots or []
            print(f'\nAnnotations on page {i+1}: {len(annots)}')
            for a in annots[:15]:
                ft = a.get('FT', '')
                v = a.get('V', '')
                t = a.get('T', '')
                print(f'  FT={ft!r}  V={v!r}  T={t!r}')
