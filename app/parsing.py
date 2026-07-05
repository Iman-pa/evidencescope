import pdfplumber


def parse_pdf(path: str) -> list[dict]:
    """Extract text page-by-page from a PDF.

    Returns a list of {"page_number": int, "text": str}, one dict per page.
    Pages with no extractable text (e.g. scanned images) return an empty
    string rather than raising an exception.
    """
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append({"page_number": i, "text": text})
    return pages
