# EvidenceScope

Evidence-linked multi-criteria decision analysis (MCDA) for health technology reimbursement review.

Given a public HTA report (PDF), EvidenceScope extracts evidence for six fixed criteria, suggests a 1–9 score per criterion with a page citation back to the source, and lets a human reviewer override any score or weight before computing a weighted total. Every score is traceable to either extracted evidence or a logged human decision.

## What it does

- Uploads one or more HTA PDFs and sends them to Claude for structured evidence extraction
- Scores six fixed criteria on a 1–9 scale with citations and confidence ratings
- Runs a verification pass: flags any criterion where the suggested score appears directionally inconsistent with the extracted evidence
- Lets reviewers override any score or weight via sliders; all changes are logged to an audit trail (SQLite)
- Computes a SMART-style weighted sum normalized to a 1–9 display score
- Supports cross-drug comparison: save two or more completed analyses, then rank them side-by-side using TOPSIS (pyDecision)
- Exports a full scorecard as Markdown, including weights, audit trail, and any verification flags

## The six criteria (fixed — do not change without discussion)

| Key | Label | What it measures |
|-----|-------|-----------------|
| `clinical_benefit` | Clinical Benefit | Comparative effectiveness vs. current standard of care |
| `safety` | Safety | Harms, adverse events, tolerability |
| `cost_effectiveness` | Cost-Effectiveness | Cost per unit of health benefit (e.g., cost/QALY) |
| `budget_impact` | Budget Impact | Net effect on payer budget if adopted |
| `equity_access` | Equity & Access | Effect on underserved or high-need populations |
| `feasibility` | Feasibility | Practicality of delivering/implementing the technology |

## Stack

- **Backend**: Python 3.11, FastAPI, pdfplumber, Anthropic Claude API (`claude-sonnet-4-6`), pyDecision, SQLite
- **Frontend**: React 18, Vite
- **Tests**: pytest, FastAPI TestClient (mocked API calls — no cost to run tests)

## Setup

```bash
# 1. Clone and enter the project
cd evidencescope

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set your Anthropic API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...

# 4. Install frontend dependencies
cd frontend && npm install && cd ..
```

## Running locally

```bash
# Terminal 1 — backend (port 8001)
uvicorn app.main:app --port 8001 --reload

# Terminal 2 — frontend dev server (port 5173)
cd frontend && npm run dev
```

Open http://localhost:5173

## Running tests

```bash
python -m pytest tests/ -v
```

All tests mock the Claude API — no API key needed and no cost incurred. Tests that read real PDFs from `data/input/` are skipped automatically if those files are absent.

## Validation

Three real CDA-AMC final reimbursement recommendations (Kerendia, Imaavy, Ebglyss) were run through the full pipeline and compared against the published committee rationale for each criterion. See [validation_report.md](validation_report.md) for findings.

## Known limitations

### In-memory state
Analysis state (scores, weights, criteria results) is held in a Python dict in the server process. **It is lost on server restart.** The SQLite audit log persists across restarts, but the analysis itself does not. For the current prototype this is acceptable; a production version would persist analyses to a database.

### Single-session comparison
Cross-drug comparison (`/compare`) requires all analyses to be in the current server session. If you restart the server between analyzing Drug A and Drug B, you cannot compare them without re-running both analyses.

### Page citations are physical PDF page numbers
Citations reference the physical page index (page 1 = the first page of the PDF file), not any printed page numbers that may appear in the document. Some HTA reports have front matter that shifts printed numbers relative to physical positions.

### Extraction quality depends on PDF text layer
EvidenceScope extracts text with pdfplumber. Scanned PDFs without an OCR layer will produce near-zero text and an error message. Redacted sections of a document will not yield evidence for those sections.

### Verification flags are advisory
The verification pass (a second Claude call that checks score–evidence consistency) is a heuristic check, not ground truth. It may miss real mismatches or flag calibration differences that are reasonable. All flags should be reviewed by a human.

### No patient data
This tool processes public HTA documents only. No patient-level data is used or accepted at any point.

## Cost per analysis

Each analysis runs 3–4 Claude API calls (extraction chunks + one verification pass). Approximate cost per 50-page document: **$0.15–$0.25** using claude-sonnet-4-6 at current pricing ($3/MTok input, $15/MTok output). Shown in server logs as `approx_cost_usd`.

## Design principles

- **Decision support, not decision-making.** Every score must trace to either extracted evidence (with a page citation) or a logged human override (with a timestamp). No score can appear without one of these two provenances.
- **Transparency over convenience.** Verification flags, audit trails, and confidence ratings are always visible. Nothing is hidden to make the output look cleaner.
- **Public documents only.** Only HTA reports and similar public evidence documents are processed. No patient data, no proprietary clinical trial data.
