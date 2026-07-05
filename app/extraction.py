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
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

CHUNK_WORD_THRESHOLD = 8_000  # words per API call
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1_500
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

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
- "citation": closest page number or section heading found in the text (e.g. "Page 12" or "Section 4.2")
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
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prefix + user_message}],
        )
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
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
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
            f"[Page {p['page_number']}]\n{p['text']}" for p in chunk if p["text"]
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
    merged["_token_usage"] = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "chunks": len(chunks),
        "approx_cost_usd": round(
            (total_input_tokens / 1_000_000) * 3.0
            + (total_output_tokens / 1_000_000) * 15.0,
            4,
        ),
    }

    return merged
