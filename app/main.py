"""EvidenceScope FastAPI application.

Endpoints
---------
GET  /health       — liveness check
POST /analyze      — upload HTA PDFs, extract evidence, return initial scores
POST /override     — record a human score/weight change, recompute total
POST /compare      — rank multiple saved analyses using TOPSIS
"""

import os
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from app.audit import get_audit_trail, log_analyze_request, log_override
from app.extraction import ExtractionError, extract_evidence
from app.models import CRITERIA, CRITERIA_DEFS
from app.parsing import parse_pdf
from app.scoring import compute_weighted_score
from app.security import enforce_rate_limits, get_client_ip, verify_demo_access

# numpy/matplotlib/pyDecision are imported lazily inside compare() below, not
# here at module load. Measured locally: importing them costs ~226MB of RSS
# (pyDecision alone pulls in pandas, scipy, scikit-learn, flask, the openai
# and google-genai SDKs, and networkx — none of which this app uses for
# anything besides one TOPSIS call). On a 512MB Render instance, paying that
# cost at startup for every request — including /health and /analyze, which
# never touch this code path — leaves dangerously little headroom. Deferring
# the import means only /compare pays for it, and only when it's actually used.

app = FastAPI(title="EvidenceScope API")

# Origins beyond localhost dev (e.g. the deployed Vercel frontend) are supplied
# via ALLOWED_ORIGINS, a comma-separated list, so this never needs a hardcoded
# production URL in source. Trailing slashes are stripped — the browser's
# Origin header never has one, so a stray "/" here would silently fail every
# CORS check (Origin exact-match) and every request would look like a network
# error ("Failed to fetch") in the browser rather than a helpful 403.
_extra_origins = [
    o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:4173",  # Vite preview
        "http://127.0.0.1:5173",
        *_extra_origins,
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory state store  {analysis_id: AnalysisState}
# Holds the extraction results + current scores/weights for each session.
# Override history is persisted separately in SQLite (app/audit.py).
# NOTE: this state is lost on server restart — by design for this prototype.
# ---------------------------------------------------------------------------

# Initialised on the same percentage scale the frontend uses (0–100).
_EQUAL_WEIGHTS: dict[str, float] = {k: 100 / len(CRITERIA) for k in CRITERIA}


class AnalysisState:
    __slots__ = ("criteria_results", "current_scores", "current_weights", "has_conflicts", "label")

    def __init__(
        self,
        criteria_results: dict,
        current_scores: dict[str, float],
        current_weights: dict[str, float],
        has_conflicts: bool,
        label: str = "",
    ):
        self.criteria_results = criteria_results
        self.current_scores = current_scores
        self.current_weights = current_weights
        self.has_conflicts = has_conflicts
        self.label = label


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


@app.post("/auth/verify", dependencies=[Depends(verify_demo_access)])
def verify_access():
    """Cheap check the frontend's password gate uses to validate a code before
    revealing the app. No Claude call, no rate limiting — just the header check."""
    return {"status": "ok"}


@app.post("/analyze", dependencies=[Depends(verify_demo_access)])
async def analyze(request: Request, files: list[UploadFile] = File(...)):
    """Upload one or more HTA PDF files and receive extracted evidence + initial scores."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")

    client_ip = get_client_ip(request)
    enforce_rate_limits(client_ip)

    # Derive label from first filename (stem, no extension)
    first_name = files[0].filename or ""
    label = Path(first_name).stem if first_name else "Untitled"

    all_pages: list[list[dict]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            if not upload.filename or not upload.filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{upload.filename}' does not appear to be a PDF.",
                )
            tmp_path = Path(tmpdir) / upload.filename
            # Stream to disk in chunks rather than buffering the whole upload
            # in memory at once (`await upload.read()` with no size limit).
            with tmp_path.open("wb") as f:
                while chunk := await upload.read(1024 * 1024):
                    f.write(chunk)
            try:
                # Runs in a worker thread so parsing a large PDF doesn't block
                # the event loop — see the note on extract_evidence() below.
                pages = await run_in_threadpool(parse_pdf, str(tmp_path))
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not parse '{upload.filename}': {exc}",
                )
            all_pages.append(pages)

    merged = _merge_pages(all_pages)
    total_chars = sum(len(p["text"]) for p in merged)
    if total_chars < 200:
        raise HTTPException(
            status_code=400,
            detail=(
                "Very little text could be extracted from the uploaded PDFs "
                f"({total_chars} characters total). "
                "The file may be a scanned image without an OCR layer, "
                "or may be corrupt. Please check the file and try again."
            ),
        )

    try:
        # extract_evidence() makes several sequential, blocking Claude API
        # calls (60-140s total). Running it directly here would block this
        # worker's entire event loop for that whole time — no other request,
        # including Render's own health checks, could be served in the
        # meantime. run_in_threadpool offloads it to a worker thread instead.
        extraction = await run_in_threadpool(extract_evidence, merged, CRITERIA_DEFS)
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=f"Evidence extraction failed: {exc}")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during evidence extraction: {type(exc).__name__}: {exc}",
        )

    approx_cost_usd = extraction.get("_token_usage", {}).get("approx_cost_usd", 0.0)
    log_analyze_request(ip=client_ip, approx_cost_usd=approx_cost_usd)

    extraction.pop("_token_usage", None)
    has_conflicts = extraction.pop("has_conflicts", False)
    extraction.pop("conflicts", None)

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
        label=label,
    )

    return {
        "analysis_id": analysis_id,
        "label": label,
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
    def new_value_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("new_value must be >= 0.")
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
    else:
        old_value = state.current_weights[req.criterion_key]
        # Guard: at least one criterion must retain a non-zero weight.
        prospective = {**state.current_weights, req.criterion_key: req.new_value}
        if all(v == 0 for v in prospective.values()):
            raise HTTPException(
                status_code=400,
                detail="At least one criterion weight must be non-zero.",
            )
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


# ---------------------------------------------------------------------------
# /compare — multi-drug TOPSIS ranking
# ---------------------------------------------------------------------------

class CompareItem(BaseModel):
    analysis_id: str
    label: str = ""  # optional override for the analysis label


class CompareRequest(BaseModel):
    comparisons: list[CompareItem]

    @field_validator("comparisons")
    @classmethod
    def need_at_least_two(cls, v: list) -> list:
        if len(v) < 2:
            raise ValueError("At least 2 analyses are required for comparison.")
        return v


@app.post("/compare")
def compare(req: CompareRequest):
    """Rank multiple saved analyses using TOPSIS (pyDecision).

    Uses the current scores and weights from each stored AnalysisState.
    Weights are averaged across all analyses for a neutral comparison baseline.
    """
    import matplotlib

    matplotlib.use("Agg")  # non-interactive backend — suppress any plot output from pyDecision
    import numpy as np
    from pyDecision.algorithm import topsis_method

    resolved: list[tuple[str, str, AnalysisState]] = []
    for item in req.comparisons:
        state = _analyses.get(item.analysis_id)
        if state is None:
            raise HTTPException(
                status_code=404, detail=f"Analysis not found: {item.analysis_id}"
            )
        label = item.label or state.label or item.analysis_id[:8]
        resolved.append((item.analysis_id, label, state))

    # Score matrix: rows = alternatives, cols = criteria (in CRITERIA order)
    matrix = np.array(
        [[state.current_scores.get(k, 5.0) for k in CRITERIA] for _, _, state in resolved],
        dtype=float,
    )

    # Average weights across analyses, then normalize to sum to 1
    avg_weights = np.array(
        [
            np.mean([state.current_weights.get(k, 100.0 / len(CRITERIA)) for _, _, state in resolved])
            for k in CRITERIA
        ],
        dtype=float,
    )
    weight_sum = avg_weights.sum()
    if weight_sum == 0:
        avg_weights = np.ones(len(CRITERIA)) / len(CRITERIA)
    else:
        avg_weights = avg_weights / weight_sum

    criterion_type = ["+"] * len(CRITERIA)  # all criteria: higher score = better for adoption

    topsis_scores = topsis_method(
        matrix, avg_weights.tolist(), criterion_type, graph=False, verbose=False
    )

    # TOPSIS degenerates to NaN when all alternatives have identical scores
    # (ideal == anti-ideal → division by zero). Fall back to weighted sum in that case.
    if any(np.isnan(s) for s in topsis_scores):
        topsis_scores = np.array([
            compute_weighted_score(state.current_scores, state.current_weights)
            for _, _, state in resolved
        ])

    ranking = sorted(
        [
            {
                "rank": 0,
                "analysis_id": aid,
                "label": label,
                "topsis_score": round(float(topsis_scores[i]), 4),
            }
            for i, (aid, label, _) in enumerate(resolved)
        ],
        key=lambda x: x["topsis_score"],
        reverse=True,
    )
    for i, item in enumerate(ranking):
        item["rank"] = i + 1

    per_criterion = {
        k: {label: float(state.current_scores.get(k, 5.0)) for _, label, state in resolved}
        for k in CRITERIA
    }

    return {
        "ranking": ranking,
        "per_criterion": per_criterion,
        "criteria": CRITERIA,
    }
