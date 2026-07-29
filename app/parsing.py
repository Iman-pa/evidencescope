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
            # pdfplumber caches each page's parsed objects (chars, rects, layout
            # structures) and doesn't release them until the PDF is closed.
            # Flushing after each page keeps memory flat across many pages
            # instead of growing for the whole document.
            page.flush_cache()
    return pages
