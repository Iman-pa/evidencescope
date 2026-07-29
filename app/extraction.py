"""Evidence extraction via Claude API.

Main entry point:
    extract_evidence(pages, criteria_defs) -> dict

`pages` is the direct output of parse_pdf() — a list of {"page_number": int, "text": str}.
`criteria_defs` is the CRITERIA_DEFS list from models.py.

For documents above the CHUNK_WORD_THRESHOLD, the text is split into page-aligned chunks
and each chunk is sent to the Claude API separately. Per-criterion results are merged
across chunks keeping the highest-confidence extraction; conflicting high-confidence
extractions are preserved rather than silently discarded.
"""

import json
import os
import re
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

CHUNK_WORD_THRESHOLD = 8_000  # words per API call
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1_500
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

# CDA-AMC reports embed a barcode/watermark footer on every page in the form
# "Combined Review for Drug (Brand) 111222" where the trailing number is a machine
# encoding of the physical page number — NOT a human-readable page reference. pdfplumber
# extracts these as literal digits, which could mislead Claude into citing garbage numbers.
# The pattern is specific to CDA-AMC's "Combined Review for ..." footer line.
_BARCODE_FOOTER_RE = re.compile(
    r"^Combined\s+Review\s+for\s+.+\(.+\)\s+\d{3,}\s*$", re.MULTILINE | re.IGNORECASE
)


def _strip_barcode_footers(text: str) -> str:
    """Remove CDA-AMC barcode/watermark footer lines before sending page text to Claude."""
    return _BARCODE_FOOTER_RE.sub("", text)


MAX_VERIFY_TOKENS = 400

_VERIFY_SYSTEM_PROMPT = """\
You are verifying evidence extraction results for a health technology reimbursement \
decision-support tool. Respond with ONLY a valid JSON object — no prose, no fences.\
"""

_VERIFY_USER_TEMPLATE = """\
Review whether each suggested_score is directionally consistent with the evidence.

Scale: 1 = strongly unfavourable for adoption, 5 = neutral/unclear, 9 = strongly favourable.

Flag a mismatch ONLY when there is a clear directional discrepancy — for example:
- Evidence clearly describes strong clinical benefit but score is ≤ 3
- Evidence clearly describes major harms or failure but score is ≥ 7
- Evidence says "not found in document" but score ≠ 5

Do NOT flag minor calibration differences or low-confidence entries where score 5 is appropriate.

EXTRACTION RESULTS:
{results_block}

Respond with ONLY this JSON (use null for note when flag is false):
{{
  "clinical_benefit":   {{"flag": false, "note": null}},
  "safety":             {{"flag": false, "note": null}},
  "cost_effectiveness": {{"flag": false, "note": null}},
  "budget_impact":      {{"flag": false, "note": null}},
  "equity_access":      {{"flag": false, "note": null}},
  "feasibility":        {{"flag": false, "note": null}}
}}\
"""


def _build_verify_block(merged: dict, criteria_keys: list[str]) -> str:
    lines = []
    for key in criteria_keys:
        entry = merged.get(key, {})
        lines.append(
            f"{key}:\n"
            f"  evidence: {entry.get('evidence', 'N/A')}\n"
            f"  suggested_score: {entry.get('suggested_score', 5)}/9\n"
            f"  confidence: {entry.get('confidence', 'low')}"
        )
    return "\n\n".join(lines)


def _run_verification(
    client: anthropic.Anthropic,
    merged: dict,
    criteria_keys: list[str],
) -> tuple[dict, dict]:
    """Single verification call checking score-evidence consistency for all criteria.

    Returns (verification_dict, usage_dict).
    verification_dict is keyed by criterion_key → {"flag": bool, "note": str|None}.
    Returns ({}, {}) on any error so verification failure never breaks extraction.
    """
    user_message = _VERIFY_USER_TEMPLATE.format(
        results_block=_build_verify_block(merged, criteria_keys)
    )
    for attempt in range(1, 3):
        prefix = "Respond with ONLY the JSON object.\n\n" if attempt == 2 else ""
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_VERIFY_TOKENS,
                system=_VERIFY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prefix + user_message}],
            )
        except Exception:
            return {}, {}

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return json.loads(raw), usage
        except json.JSONDecodeError:
            if attempt == 2:
                return {}, {}
    return {}, {}


_SYSTEM_PROMPT = """\
You are a structured evidence extractor for a decision-support tool used in health \
technology reimbursement review. Your role is to read the provided HTA document excerpt \
and return structured evidence — not to make recommendations.

CRITICAL RULES:
1. Ground every claim ONLY in the provided text. Never use outside knowledge.
2. If the text does not clearly address a criterion, set confidence to "low". Do NOT \
fabricate an answer to avoid a low-confidence flag.
3. Respond with ONLY a valid JSON object — no markdown fences, no prose before or after.\
"""

_USER_TEMPLATE = """\
Extract evidence for each criterion from this HTA document excerpt (pages {start}–{end}).

CRITERIA:
{criteria_block}

For each criterion return EXACTLY these fields:
- "evidence": 1–2 sentence plain-language summary using ONLY the provided text
- "citation": the [Page N] marker that precedes the relevant text in the excerpt (e.g. "Page 12"). Use ONLY the [Page N] tags injected at the start of each page — do not use any numbers found inside the document body text.
- "suggested_score": integer 1–9 (1=strongly unfavourable for adoption, 5=neutral/unclear, 9=strongly favourable)
- "rationale": one sentence grounded only in the extracted evidence
- "confidence": "high" if text clearly addresses criterion | "medium" if partially | "low" if not clearly addressed

Respond with ONLY this JSON object, nothing else:
{{
  "clinical_benefit": {{"evidence": "...", "citation": "...", "suggested_score": 5, "rationale": "...", "confidence": "..."}},
  "safety": {{"evidence": "...", "citation": "...", "suggested_score": 5, "rationale": "...", "confidence": "..."}},
  "cost_effectiveness": {{"evidence": "...", "citation": "...", "suggested_score": 5, "rationale": "...", "confidence": "..."}},
  "budget_impact": {{"evidence": "...", "citation": "...", "suggested_score": 5, "rationale": "...", "confidence": "..."}},
  "equity_access": {{"evidence": "...", "citation": "...", "suggested_score": 5, "rationale": "...", "confidence": "..."}},
  "feasibility": {{"evidence": "...", "citation": "...", "suggested_score": 5, "rationale": "...", "confidence": "..."}}
}}

DOCUMENT TEXT (pages {start}–{end}):
{text}\
"""


class ExtractionError(Exception):
    pass


def _build_criteria_block(criteria_defs: list[dict]) -> str:
    lines = []
    for i, c in enumerate(criteria_defs, start=1):
        lines.append(f"{i}. {c['key']} — {c['definition']}")
    return "\n".join(lines)


def _call_claude(
    client: anthropic.Anthropic,
    user_message: str,
    chunk_label: str,
) -> dict:
    """Call Claude, retry once on JSON parse failure, raise ExtractionError on second failure."""
    for attempt in range(1, 3):
        prefix = (
            "Your previous response was not valid JSON. "
            "Respond with ONLY the JSON object, nothing else.\n\n"
            if attempt == 2
            else ""
        )
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prefix + user_message}],
            )
        except anthropic.APITimeoutError as exc:
            raise ExtractionError(f"Claude API timed out for {chunk_label}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ExtractionError(
                f"Could not connect to Claude API for {chunk_label}: {exc}"
            ) from exc
        except anthropic.RateLimitError as exc:
            raise ExtractionError(f"Claude API rate limit reached: {exc}") from exc
        except anthropic.APIError as exc:
            raise ExtractionError(f"Claude API error for {chunk_label}: {exc}") from exc
        raw = response.content[0].text.strip()

        # Strip accidental markdown fences if the model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            parsed = json.loads(raw)
            parsed["_usage"] = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            return parsed
        except json.JSONDecodeError:
            if attempt == 2:
                raise ExtractionError(
                    f"Claude returned invalid JSON after 2 attempts for {chunk_label}. "
                    f"Raw response (first 500 chars): {raw[:500]}"
                )
            # loop continues for attempt 2


def _chunk_pages(pages: list[dict], word_threshold: int) -> list[list[dict]]:
    """Split pages into chunks where each chunk is <= word_threshold words."""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_words = 0

    for page in pages:
        page_words = len(page["text"].split())
        if current and current_words + page_words > word_threshold:
            chunks.append(current)
            current = []
            current_words = 0
        current.append(page)
        current_words += page_words

    if current:
        chunks.append(current)

    return chunks


def _merge_results(chunk_results: list[dict], criteria_keys: list[str]) -> dict:
    """Merge per-chunk extractions into a single result.

    Per criterion:
    - Keep the highest-confidence extraction.
    - If two chunks both have "high" confidence with differing evidence,
      record a conflict rather than silently dropping one.
    """
    merged: dict[str, Any] = {}
    conflicts: dict[str, list[dict]] = {}

    for key in criteria_keys:
        best: dict | None = None
        for chunk in chunk_results:
            entry = chunk.get(key)
            if not entry or not isinstance(entry, dict):
                continue
            if best is None:
                best = entry
                continue
            best_rank = CONFIDENCE_RANK.get(best.get("confidence", "low"), 1)
            entry_rank = CONFIDENCE_RANK.get(entry.get("confidence", "low"), 1)
            if entry_rank > best_rank:
                best = entry
            elif (
                entry_rank == best_rank == CONFIDENCE_RANK["high"]
                and entry.get("evidence") != best.get("evidence")
            ):
                # Two high-confidence, differing — record conflict
                conflicts.setdefault(key, [best])
                conflicts[key].append(entry)

        merged[key] = best or {
            "evidence": "Not found in document.",
            "citation": "N/A",
            "suggested_score": 5,
            "rationale": "No evidence found.",
            "confidence": "low",
        }

    if conflicts:
        merged["conflicts"] = conflicts
        merged["has_conflicts"] = True
    else:
        merged["has_conflicts"] = False

    return merged


def extract_evidence(pages: list[dict], criteria_defs: list[dict]) -> dict:
    """Extract evidence for all criteria from a parsed PDF.

    Args:
        pages: Output of parse_pdf() — list of {"page_number": int, "text": str}.
        criteria_defs: CRITERIA_DEFS from models.py.

    Returns:
        dict with one key per criterion (evidence, citation, suggested_score,
        rationale, confidence) plus "has_conflicts", optional "conflicts",
        and "_token_usage" (total input/output tokens across all chunks).
    """
    # The SDK's default read timeout is 600s per call — with 2-4 sequential
    # calls per analysis, a single slow response could otherwise hang the
    # whole request for up to 10 minutes before failing. 60s is generous for
    # these prompts (max_tokens 400-1500) and ensures a slow call surfaces as
    # a clean ExtractionError instead of hanging far past any reasonable limit.
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=60.0)
    criteria_keys = [c["key"] for c in criteria_defs]
    criteria_block = _build_criteria_block(criteria_defs)

    total_words = sum(len(p["text"].split()) for p in pages)
    chunks = (
        _chunk_pages(pages, CHUNK_WORD_THRESHOLD)
        if total_words > CHUNK_WORD_THRESHOLD
        else [pages]
    )

    chunk_results: list[dict] = []
    total_input_tokens = 0
    total_output_tokens = 0

    for chunk in chunks:
        start_page = chunk[0]["page_number"]
        end_page = chunk[-1]["page_number"]
        chunk_text = "\n\n".join(
            f"[Page {p['page_number']}]\n{_strip_barcode_footers(p['text'])}"
            for p in chunk if p["text"]
        )
        chunk_label = f"pages {start_page}–{end_page}"

        user_message = _USER_TEMPLATE.format(
            start=start_page,
            end=end_page,
            criteria_block=criteria_block,
            text=chunk_text,
        )

        result = _call_claude(client, user_message, chunk_label)
        usage = result.pop("_usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        chunk_results.append(result)

    merged = _merge_results(chunk_results, criteria_keys)

    # Verification pass: one additional call checking score–evidence consistency.
    # Fails gracefully — a verification error never aborts extraction.
    verification, verify_usage = _run_verification(client, merged, criteria_keys)
    for key in criteria_keys:
        v = verification.get(key, {})
        merged[key]["verification_flag"] = bool(v.get("flag", False))
        merged[key]["verification_note"] = v.get("note") or None

    verify_in  = verify_usage.get("input_tokens", 0)
    verify_out = verify_usage.get("output_tokens", 0)
    merged["_token_usage"] = {
        "input_tokens":  total_input_tokens + verify_in,
        "output_tokens": total_output_tokens + verify_out,
        "chunks": len(chunks),
        "approx_cost_usd": round(
            ((total_input_tokens + verify_in)  / 1_000_000) * 3.0
            + ((total_output_tokens + verify_out) / 1_000_000) * 15.0,
            4,
        ),
    }

    return merged
