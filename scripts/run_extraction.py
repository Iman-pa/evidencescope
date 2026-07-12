"""Run full extraction pipeline for one PDF and save result to a fixture JSON.

Usage:
    python scripts/run_extraction.py <pdf_path> <output_fixture_path>
"""
import json
import sys
from pathlib import Path

# Make sure the app package is importable from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.extraction import extract_evidence
from app.models import CRITERIA_DEFS
from app.parsing import parse_pdf

def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/run_extraction.py <pdf_path> <output_fixture_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    out_path = sys.argv[2]

    print(f"Parsing {pdf_path} ...")
    pages = parse_pdf(pdf_path)
    total_chars = sum(len(p["text"]) for p in pages)
    total_words = sum(len(p["text"].split()) for p in pages)
    print(f"  {len(pages)} pages, {total_words:,} words, {total_chars:,} chars")

    print("Running extraction ...")
    result = extract_evidence(pages, CRITERIA_DEFS)

    usage = result.get("_token_usage", {})
    print(f"  Done. Tokens: {usage.get('input_tokens', 0):,} in / {usage.get('output_tokens', 0):,} out")
    print(f"  Approx cost: ${usage.get('approx_cost_usd', 0):.4f}")
    print(f"  Chunks: {usage.get('chunks', 1)}")
    print(f"  Has conflicts: {result.get('has_conflicts', False)}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved to {out_path}")

    # Print score summary
    from app.models import CRITERIA
    print("\nScore summary:")
    for k in CRITERIA:
        entry = result.get(k, {})
        flag = " [FLAG]" if entry.get("verification_flag") else ""
        print(f"  {k}: {entry.get('suggested_score', '?')}/9  conf={entry.get('confidence', '?')}{flag}")

if __name__ == "__main__":
    main()
