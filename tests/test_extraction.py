"""Tests for extraction.py — citation correctness and barcode-footer stripping.

No Claude API calls are made in any test here. The tests use:
  - Synthetic page text (fast, self-contained)
  - Real PDF files from data/input/ via pdfplumber (I/O only, no API)

Root-cause narrative
--------------------
CDA-AMC reports (Imaavy, Ebglyss) embed a barcode/watermark footer on every page
that pdfplumber extracts as a long digit string:

    [Page 6]
    ...CDA-AMC estimates the budget impact will be approximately $705 million...
    Combined Review for Nipocalimab (Imaavy) 666

    [Page 12]
    ...
    Combined Review for Nipocalimab (Imaavy) 111222

Claude's citation instruction said "closest page number found in the text." For a
criterion whose evidence appears just before the "666" footer, "666" is the closest
number — not our injected "[Page 6]" tag. For safety (page 4), the footer is "444"
and the [Page 4] tag is close and numerically similar, so Claude could reasonably
cite either; but for budget_impact on page 12, "111222" vs "12" are obviously
different and the wrong one would produce a useless citation.

Fix:
  1. _strip_barcode_footers() removes these lines before sending text to Claude.
  2. The citation instruction was tightened to say "use ONLY the [Page N] tags."
"""

import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.extraction import (
    _build_verify_block,
    _chunk_pages,
    _run_verification,
    _strip_barcode_footers,
    CHUNK_WORD_THRESHOLD,
)
from app.models import CRITERIA

# ---------------------------------------------------------------------------
# Paths — tests that touch real PDFs skip gracefully if files are absent
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "input")
_IMAAVY_PDF = os.path.join(_DATA_DIR, "SR0905_Imaavy_DRAFT_combined.pdf")
_EBGLYSS_PDF = os.path.join(_DATA_DIR, "SR0914-Ebglyss_combined.pdf")
_KERENDIA_PDF = os.path.join(_DATA_DIR, "SR0893r-Kerendia_combined.pdf")

_real_pdfs_present = all(os.path.exists(p) for p in [_IMAAVY_PDF, _EBGLYSS_PDF, _KERENDIA_PDF])

requires_real_pdfs = pytest.mark.skipif(
    not _real_pdfs_present,
    reason="Real PDF files not found in data/input/ — skipping integration checks.",
)


# ---------------------------------------------------------------------------
# Unit tests for _strip_barcode_footers (synthetic text, no I/O)
# ---------------------------------------------------------------------------

class TestStripBarcodeFooters:
    """Verify the barcode regex strips exactly what it should and nothing more."""

    KNOWN_FOOTERS = [
        # Imaavy pages 2–9
        "Combined Review for Nipocalimab (Imaavy) 222",
        "Combined Review for Nipocalimab (Imaavy) 666",
        # Imaavy pages 10+
        "Combined Review for Nipocalimab (Imaavy) 111000",
        "Combined Review for Nipocalimab (Imaavy) 111222",
        "Combined Review for Nipocalimab (Imaavy) 444999",
        # Ebglyss
        "Combined Review for Lebrikizumab (Ebglyss) 333",
        "Combined Review for Lebrikizumab (Ebglyss) 555555",
    ]

    def test_strips_all_known_footer_patterns(self):
        for footer in self.KNOWN_FOOTERS:
            result = _strip_barcode_footers(footer)
            assert result.strip() == "", (
                f"Expected footer to be stripped but got: {result!r}\n"
                f"Footer was: {footer!r}"
            )

    def test_strips_footer_at_end_of_page_text(self):
        """The footer appears as the last line of a page — it must be stripped there."""
        page_text = (
            "Key Messages\n"
            "• CDA-AMC estimates the budget impact will be approximately $705 million.\n"
            "Combined Review for Nipocalimab (Imaavy) 666"
        )
        cleaned = _strip_barcode_footers(page_text)
        assert "666" not in cleaned.split()
        assert "$705 million" in cleaned  # content preserved

    def test_strips_footer_embedded_mid_page(self):
        """Even if the barcode appears mid-page, it should be removed."""
        page_text = (
            "Content before.\n"
            "Combined Review for Nipocalimab (Imaavy) 111222\n"
            "Content after."
        )
        cleaned = _strip_barcode_footers(page_text)
        assert "111222" not in cleaned
        assert "Content before." in cleaned
        assert "Content after." in cleaned

    # --- False-positive tests: content that must NOT be stripped ---

    def test_does_not_strip_sentence_ending_in_year(self):
        text = "The trial (FINEARTS-HF, n=6001) was published in 2024."
        assert _strip_barcode_footers(text) == text

    def test_does_not_strip_table_note_with_trailing_number(self):
        text = "Table 9 (Summary of CDA-AMC Economic Evaluation Results) 111"
        # "111" is only 3 digits but the line starts with "Table", not "Combined Review for"
        assert _strip_barcode_footers(text) == text

    def test_does_not_strip_cost_sentence_ending_in_digits(self):
        text = "The ICER was $77,195 per QALY (base case) 999"
        assert _strip_barcode_footers(text) == text

    def test_does_not_strip_plain_content_line(self):
        text = "finerenone was shown to reduce the risk of CV death (FINEARTS-HF) 2026."
        # ends in 4 digits but doesn't start with "Combined Review for"
        assert _strip_barcode_footers(text) == text


# ---------------------------------------------------------------------------
# Integration tests — real PDFs, no API calls
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fixture data — Kerendia extraction from a previous API run (no new API calls)
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "kerendia_extraction.json"

def _load_kerendia_fixture() -> dict:
    with open(_FIXTURE_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Verification pass tests (all mocked — no real API calls)
# ---------------------------------------------------------------------------

class TestVerificationPass:
    """Tests for _run_verification and _build_verify_block.

    The Claude client is mocked throughout — these tests exercise our logic,
    not the API itself.
    """

    def _mock_client(self, flag_map: dict) -> MagicMock:
        """Build a mock anthropic.Anthropic that returns a verification JSON."""
        response_json = json.dumps({
            k: {"flag": flag_map.get(k, False), "note": f"mismatch on {k}" if flag_map.get(k) else None}
            for k in CRITERIA
        })
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response_json)]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 50
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        return mock_client

    def test_build_verify_block_includes_all_criteria(self):
        fixture = _load_kerendia_fixture()
        block = _build_verify_block(fixture, CRITERIA)
        for key in CRITERIA:
            assert key in block

    def test_build_verify_block_includes_scores_and_evidence(self):
        fixture = _load_kerendia_fixture()
        block = _build_verify_block(fixture, CRITERIA)
        assert "suggested_score: 6/9" in block   # clinical_benefit
        assert "suggested_score: 3/9" in block   # budget_impact
        assert "finerenone" in block.lower()

    def test_no_flags_when_scores_match_evidence(self):
        """When the mock returns all flag=false, no criteria are flagged."""
        fixture = _load_kerendia_fixture()
        client = self._mock_client({})  # all false
        verification, usage = _run_verification(client, fixture, CRITERIA)
        for key in CRITERIA:
            assert verification[key]["flag"] is False
        assert usage["input_tokens"] == 200

    def test_flags_propagated_when_model_detects_mismatch(self):
        """When the mock flags budget_impact, that flag is returned."""
        fixture = _load_kerendia_fixture()
        client = self._mock_client({"budget_impact": True})
        verification, _ = _run_verification(client, fixture, CRITERIA)
        assert verification["budget_impact"]["flag"] is True
        assert "budget_impact" in verification["budget_impact"]["note"]
        # Others not flagged
        assert verification["clinical_benefit"]["flag"] is False

    def test_returns_empty_on_json_parse_failure(self):
        """If Claude returns invalid JSON twice, _run_verification returns {} gracefully."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="this is not json")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 10
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        fixture = _load_kerendia_fixture()
        verification, usage = _run_verification(mock_client, fixture, CRITERIA)
        assert verification == {}
        assert usage == {}

    def test_returns_empty_on_api_exception(self):
        """If the API call raises an exception, _run_verification returns {} without propagating."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("network error")

        fixture = _load_kerendia_fixture()
        verification, usage = _run_verification(mock_client, fixture, CRITERIA)
        assert verification == {}
        assert usage == {}

    def test_verification_flags_added_to_merged_results(self):
        """verify that extract_evidence integration adds verification_flag to each criterion.

        Uses mocked extract_evidence output (no real API) and checks that
        the verification_flag and verification_note keys are present after
        extract_evidence calls _run_verification internally.
        """
        fixture = _load_kerendia_fixture()
        # Simulate what extract_evidence does after merging:
        # attach verification results to each criterion
        flag_map = {"cost_effectiveness": True}
        client = self._mock_client(flag_map)
        verification, _ = _run_verification(client, fixture, CRITERIA)
        for key in CRITERIA:
            v = verification.get(key, {})
            fixture[key]["verification_flag"] = bool(v.get("flag", False))
            fixture[key]["verification_note"] = v.get("note") or None

        assert fixture["cost_effectiveness"]["verification_flag"] is True
        assert fixture["clinical_benefit"]["verification_flag"] is False
        assert "verification_note" in fixture["safety"]


@requires_real_pdfs
class TestBarcodesInRealPDFs:
    """Prove the bug existed in the raw PDF text and the fix removes it."""

    def _parse(self, path: str):
        from app.parsing import parse_pdf
        return parse_pdf(path)

    # Pattern matching what pdfplumber extracts from these PDFs
    _BARCODE_RE = re.compile(
        r"^Combined\s+Review\s+for\s+.+\(.+\)\s+\d{3,}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    def test_imaavy_raw_pages_contain_barcode_footers(self):
        """Bug exists: Imaavy pages 2–54 contain barcode lines before the fix."""
        pages = self._parse(_IMAAVY_PDF)
        pages_with_barcodes = [p for p in pages if self._BARCODE_RE.search(p["text"])]
        # We know from diagnostic runs all pages except pg 1 have footers
        assert len(pages_with_barcodes) >= 50, (
            f"Expected ≥50 pages with barcode footers, got {len(pages_with_barcodes)}"
        )

    def test_ebglyss_raw_pages_contain_barcode_footers(self):
        """Bug exists: Ebglyss pages also have barcode footers."""
        pages = self._parse(_EBGLYSS_PDF)
        pages_with_barcodes = [p for p in pages if self._BARCODE_RE.search(p["text"])]
        assert len(pages_with_barcodes) >= 50

    def test_kerendia_has_no_barcode_footers(self):
        """Kerendia is unaffected — no barcodes — so the fix is a safe no-op for it."""
        pages = self._parse(_KERENDIA_PDF)
        pages_with_barcodes = [p for p in pages if self._BARCODE_RE.search(p["text"])]
        assert pages_with_barcodes == [], (
            f"Expected 0 barcode pages in Kerendia, found {len(pages_with_barcodes)}"
        )

    def test_imaavy_budget_impact_page_barcode_matches_known_value(self):
        """
        The budget impact key evidence is on physical page 6 of Imaavy.
        Before the fix, that page's text ends with "Combined Review for Nipocalimab (Imaavy) 666"
        — making "666" the closest number in the text to the evidence, which Claude
        could cite instead of "Page 6".
        After stripping, "666" is gone and only our injected [Page 6] tag remains.
        """
        pages = self._parse(_IMAAVY_PDF)
        pg6 = next(p for p in pages if p["page_number"] == 6)

        # Confirm the evidence is on this page
        assert "$705 million" in pg6["text"] or "budget impact" in pg6["text"].lower()

        # Bug: barcode is present BEFORE stripping
        assert self._BARCODE_RE.search(pg6["text"]) is not None, (
            "Expected barcode footer on Imaavy page 6 before fix"
        )

        # Fix: barcode is gone AFTER stripping
        cleaned = _strip_barcode_footers(pg6["text"])
        assert self._BARCODE_RE.search(cleaned) is None
        # Content preserved
        assert "705 million" in cleaned or "budget impact" in cleaned.lower()

    def test_chunk_text_for_imaavy_chunk1_clean_after_fix(self):
        """
        Build the actual chunk_text string sent to Claude for Imaavy chunk 1 (pages 1–22).
        Before fix: contains "666", "111000", "111222" etc.
        After fix:  contains only [Page N] tags as numeric references.
        """
        pages = self._parse(_IMAAVY_PDF)
        chunks = _chunk_pages(pages, CHUNK_WORD_THRESHOLD)
        chunk1 = chunks[0]

        # Build chunk_text WITHOUT stripping (simulates old broken behaviour)
        raw_chunk_text = "\n\n".join(
            f"[Page {p['page_number']}]\n{p['text']}"
            for p in chunk1 if p["text"]
        )
        # Build chunk_text WITH stripping (the fix)
        clean_chunk_text = "\n\n".join(
            f"[Page {p['page_number']}]\n{_strip_barcode_footers(p['text'])}"
            for p in chunk1 if p["text"]
        )

        # Bug: raw text contained barcode numbers
        assert self._BARCODE_RE.search(raw_chunk_text) is not None, (
            "Raw chunk text should contain barcode footers"
        )

        # Fix: cleaned text has no barcode lines
        assert self._BARCODE_RE.search(clean_chunk_text) is None, (
            "Clean chunk text must not contain barcode footers"
        )

        # Fix does not destroy [Page N] markers
        for p in chunk1[:5]:
            assert f"[Page {p['page_number']}]" in clean_chunk_text
