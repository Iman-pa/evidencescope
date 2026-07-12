"""Read holdout PDFs and print full text for extraction comparison."""
import sys
import pdfplumber

def read_pdf(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append((i, text))
    return pages

sys.stdout.reconfigure(encoding='utf-8')

for path in sys.argv[1:]:
    print(f"\n{'='*80}")
    print(f"FILE: {path}")
    print('='*80)
    pages = read_pdf(path)
    for num, text in pages:
        print(f"\n--- Page {num} ---")
        print(text)
