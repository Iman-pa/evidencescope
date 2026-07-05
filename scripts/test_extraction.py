"""Run extract_evidence() on a single PDF and print the full result + token usage.

Usage (from repo root):
    python scripts/test_extraction.py data/input/SR0893r-Kerendia_combined.pdf
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extraction import extract_evidence
from app.models import CRITERIA_DEFS
from app.parsing import parse_pdf


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_extraction.py <path/to/file.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Parsing: {pdf_path}")
    pages = parse_pdf(pdf_path)
    total_words = sum(len(p["text"].split()) for p in pages)
    print(f"  {len(pages)} pages, ~{total_words:,} words")
    print("Calling Claude API...")

    result = extract_evidence(pages, CRITERIA_DEFS)

    usage = result.pop("_token_usage", {})
    has_conflicts = result.pop("has_conflicts", False)
    conflicts = result.pop("conflicts", {})

    print("\n" + "=" * 70)
    print("EXTRACTION RESULT")
    print("=" * 70)
    print(json.dumps(result, indent=2))

    if has_conflicts:
        print("\n" + "=" * 70)
        print("CONFLICTS DETECTED")
        print("=" * 70)
        print(json.dumps(conflicts, indent=2))

    print("\n" + "=" * 70)
    print("TOKEN USAGE")
    print("=" * 70)
    print(f"  Chunks:         {usage.get('chunks')}")
    print(f"  Input tokens:   {usage.get('input_tokens'):,}")
    print(f"  Output tokens:  {usage.get('output_tokens'):,}")
    print(f"  Approx cost:    ${usage.get('approx_cost_usd'):.4f}")


if __name__ == "__main__":
    main()
