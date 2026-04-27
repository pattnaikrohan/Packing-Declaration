from app.ingestion import ocr_extractor
with open(r'd:\Packing Declaration\PKD-FRE.pdf', 'rb') as f:
    file_bytes = f.read()
img = ocr_extractor._load_images_from_pdf(file_bytes)[0]
g, t = ocr_extractor._preprocess_image(img)
txt, _, _ = ocr_extractor._ocr_image(g)
print(repr(txt))
