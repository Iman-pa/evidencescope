"""EvidenceScope FastAPI application.

Endpoints
---------
GET  /health       — liveness check
POST /analyze      — upload HTA PDFs, extract evidence, return initial scores
POST /override     — record a human score/weight change, recompute total
"""

import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app.audit import get_audit_trail, log_override
from app.extraction import ExtractionError, extract_evidence
from app.models import CRITERIA, CRITERIA_DEFS
from app.parsing import parse_pdf
from app.scoring import compute_weighted_score

app = FastAPI(title="EvidenceScope API")

# ---------------------------------------------------------------------------
# In-memory state store  {analysis_id: AnalysisState}
# Holds the extraction results + current scores/weights for each session.
# Override history is persisted separately in SQLite (app/audit.py).
# ---------------------------------------------------------------------------

_EQUAL_WEIGHTS: dict[str, float] = {k: 1.0 for k in CRITERIA}


class AnalysisState:
    __slots__ = ("criteria_results", "current_scores", "current_weights", "has_conflicts")

    def __init__(
        self,
        criteria_results: dict,
        current_scores: dict[str, float],
        current_weights: dict[str, float],
        has_conflicts: bool,
    ):
        self.criteria_results = criteria_results
        self.current_scores = current_scores
        self.current_weights = current_weights
        self.has_conflicts = has_conflicts


_analyses: dict[str, AnalysisState] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_pages(page_lists: list[list[dict]]) -> list[dict]:
    """Concatenate pages from multiple PDFs, renumbering sequentially."""
    merged = []
    offset = 0
    for pages in page_lists:
        for p in pages:
            merged.append({"page_number": offset + p["page_number"], "text": p["text"]})
        offset += pages[-1]["page_number"] if pages else 0
    return merged


def _scores_from_extraction(criteria_results: dict) -> dict[str, float]:
    return {
        k: float(criteria_results[k].get("suggested_score", 5))
        for k in CRITERIA
        if k in criteria_results
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(files: list[UploadFile] = File(...)):
    """Upload one or more HTA PDF files and receive extracted evidence + initial scores."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")

    # Parse each uploaded file via a named temp file (pdfplumber needs a path)
    all_pages: list[list[dict]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            if not upload.filename or not upload.filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{upload.filename}' does not appear to be a PDF.",
                )
            tmp_path = Path(tmpdir) / upload.filename
            tmp_path.write_bytes(await upload.read())
            try:
                pages = parse_pdf(str(tmp_path))
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not parse '{upload.filename}': {exc}",
                )
            all_pages.append(pages)

    merged = _merge_pages(all_pages)
    total_chars = sum(len(p["text"]) for p in merged)
    if total_chars == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No text could be extracted from the uploaded PDFs. "
                "Files may be scanned images without an OCR layer."
            ),
        )

    try:
        extraction = extract_evidence(merged, CRITERIA_DEFS)
    except ExtractionError as exc:
        raise HTTPException(status_code=500, detail=f"Evidence extraction failed: {exc}")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during evidence extraction: {type(exc).__name__}: {exc}",
        )

    token_usage = extraction.pop("_token_usage", None)
    has_conflicts = extraction.pop("has_conflicts", False)
    extraction.pop("conflicts", None)  # conflicts included in criteria_results below

    # Build clean per-criterion results (only the 6 criteria keys)
    criteria_results = {k: extraction[k] for k in CRITERIA if k in extraction}
    current_scores = _scores_from_extraction(criteria_results)
    current_weights = dict(_EQUAL_WEIGHTS)

    initial_weighted_score = compute_weighted_score(current_scores, current_weights)

    analysis_id = str(uuid.uuid4())
    _analyses[analysis_id] = AnalysisState(
        criteria_results=criteria_results,
        current_scores=current_scores,
        current_weights=current_weights,
        has_conflicts=has_conflicts,
    )

    return {
        "analysis_id": analysis_id,
        "criteria_results": criteria_results,
        "current_scores": current_scores,
        "current_weights": current_weights,
        "initial_weighted_score": round(initial_weighted_score, 6),
        "has_conflicts": has_conflicts,
    }


class OverrideRequest(BaseModel):
    analysis_id: str
    criterion_key: str
    field: Literal["score", "weight"]
    new_value: float

    @field_validator("criterion_key")
    @classmethod
    def criterion_key_must_be_valid(cls, v: str) -> str:
        if v not in CRITERIA:
            raise ValueError(f"criterion_key '{v}' is not a valid criterion. Valid: {CRITERIA}")
        return v

    @field_validator("new_value")
    @classmethod
    def new_value_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("new_value must be positive.")
        return v


@app.post("/override")
def override(req: OverrideRequest):
    """Record a human override to a score or weight and recompute the weighted total."""
    state = _analyses.get(req.analysis_id)
    if state is None:
        raise HTTPException(
            status_code=404, detail=f"Analysis not found: {req.analysis_id}"
        )

    if req.field == "score":
        if not (1.0 <= req.new_value <= 9.0):
            raise HTTPException(
                status_code=400,
                detail=f"Score must be in [1, 9]; got {req.new_value}.",
            )
        old_value = state.current_scores[req.criterion_key]
        state.current_scores[req.criterion_key] = req.new_value
    else:  # weight
        old_value = state.current_weights[req.criterion_key]
        state.current_weights[req.criterion_key] = req.new_value

    log_override(
        analysis_id=req.analysis_id,
        criterion_key=req.criterion_key,
        old_value=old_value,
        new_value=req.new_value,
        field=req.field,
    )

    updated_score = compute_weighted_score(state.current_scores, state.current_weights)
    audit_trail = get_audit_trail(req.analysis_id)

    return {
        "analysis_id": req.analysis_id,
        "criterion_key": req.criterion_key,
        "field": req.field,
        "old_value": old_value,
        "new_value": req.new_value,
        "updated_weighted_score": round(updated_score, 6),
        "audit_trail": audit_trail,
    }
