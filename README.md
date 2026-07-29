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

## Deploying the live demo

The demo deployment is two separate services: the FastAPI backend on Render
and the React frontend on Vercel. Both are gated behind `DEMO_ACCESS_CODE` and
a per-IP / global daily analysis cap (see [Demo access control](#demo-access-control)
below) to keep Claude API usage bounded.

### 1. Backend — Render

1. Push this repo to GitHub if it isn't already there.
2. Go to [render.com](https://render.com) and sign in (GitHub login is easiest).
3. **New +** → **Blueprint** → connect this GitHub repo. Render will detect
   `render.yaml` at the repo root and propose one service, `evidencescope-api`.
4. Before the first deploy, Render will prompt for the env vars marked
   `sync: false` in `render.yaml`. Set:
   - `ANTHROPIC_API_KEY` — your real Claude API key
   - `DEMO_ACCESS_CODE` — the demo access code (e.g. `EvidenceScope138`)
   - `ALLOWED_ORIGINS` — leave blank for now; you'll set this after step 2
     below once you know the Vercel URL (comma-separated if more than one)
5. Deploy. First build takes a few minutes. Once live, note the backend URL
   (e.g. `https://evidencescope-api.onrender.com`) — you'll need it for the
   frontend.
6. Sanity check: `curl https://<your-backend>.onrender.com/health` should
   return `{"status":"ok"}`.

**Free-tier notes:**
- The service spins down after ~15 minutes of inactivity and takes up to
  ~50 seconds to wake on the next request. The frontend's password gate
  pings `/health` on load and shows a "waking up" message if the server
  doesn't respond quickly, so this doesn't look broken — but it does mean
  the very first analysis after a period of inactivity can take noticeably
  longer than the usual 60–90 seconds. If a request ever times out for this
  reason, retrying immediately after works, since the server is warm by then.
- Analysis state (in-memory) and the SQLite audit log both reset whenever the
  service restarts or redeploys — this is a known limitation of the current
  architecture (see below), not specific to Render.

### 2. Frontend — Vercel

1. Go to [vercel.com](https://vercel.com) and sign in.
2. **Add New** → **Project** → import this same GitHub repo as a **new,
   separate** Vercel project (don't reuse an existing portfolio project).
3. When configuring the project:
   - **Root Directory**: `frontend`
   - Framework preset: Vite (should be auto-detected)
   - Build command / output directory: leave the Vite defaults
4. Add an environment variable: `VITE_API_URL` = the Render backend URL from
   step 1 (e.g. `https://evidencescope-api.onrender.com`, no trailing slash).
5. Deploy. Note the resulting URL (e.g. `https://evidencescope.vercel.app`).
6. Back in Render, set `ALLOWED_ORIGINS` on the backend service to this
   Vercel URL and redeploy the backend (or trigger a manual restart) so CORS
   allows requests from it.

### Demo access control

- `POST /analyze` (and the cheap `POST /auth/verify` the frontend's password
  gate uses to validate a code) require a matching `X-Demo-Key` header when
  `DEMO_ACCESS_CODE` is set. Unset locally, this check is skipped entirely.
- Rate limits: `RATE_LIMIT_PER_IP_PER_DAY` (default 5) and
  `RATE_LIMIT_GLOBAL_PER_DAY` (default 30), both rolling 24h windows, enforced
  before any Claude API call is made. Hitting either returns a friendly 429
  with the message "Demo limit reached for today...".
- Every completed analysis is logged (timestamp, IP, approximate cost) to the
  same SQLite audit database used for the override trail.

## Validation

Three real CDA-AMC final reimbursement recommendations (Kerendia, Imaavy, Ebglyss) were run through the full pipeline and compared against the published committee rationale for each criterion. See [validation_report.md](validation_report.md) for findings.

## Known limitations

### In-memory state
Analysis state (scores, weights, criteria results) is held in a Python dict in the server process. **It is lost on server restart.** The SQLite audit log persists across restarts, but the analysis itself does not. For the current prototype this is acceptable; a production version would persist analyses to a database. On the deployed demo (Render free tier), this also means state is lost whenever the service spins down after inactivity and wakes on the next request.

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
