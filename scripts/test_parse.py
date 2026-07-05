"""Sanity-check script: run parse_pdf() on every PDF in data/input/ and data/holdout/.

Usage (from repo root):
    python scripts/test_parse.py
"""

import sys
from pathlib import Path

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.parsing import parse_pdf

DATA_DIRS = [
    Path("data/input"),
    Path("data/holdout"),
]


def check_dir(directory: Path) -> None:
    pdfs = sorted(directory.glob("*.pdf"))
    if not pdfs:
        print(f"[{directory}]  no PDFs found\n")
        return

    for pdf_path in pdfs:
        pages = parse_pdf(str(pdf_path))
        total_chars = sum(len(p["text"]) for p in pages)
        first_page_text = pages[0]["text"][:300] if pages else ""
        print(f"[{directory / pdf_path.name}]")
        print(f"  total pages : {len(pages)}")
        print(f"  total chars : {total_chars}")
        print(f"  page 1 preview:")
        print(f"    {first_page_text!r}")
        print()


def main() -> None:
    for d in DATA_DIRS:
        check_dir(d)


if __name__ == "__main__":
    main()
