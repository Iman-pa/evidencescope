# EvidenceScope
An evidence-linked MCDA (multi-criteria decision analysis) tool for health technology
reimbursement review. Given a real HTA report (PDF), it extracts evidence for 6 fixed
criteria, suggests a 1-9 score per criterion with a citation back to the source page,
and lets a human review/override every score before computing a weighted total.

Design commitment: this is DECISION SUPPORT, not decision-making. Every score must be
traceable to either (a) extracted evidence with a citation, or (b) a logged human
override with a timestamp. No score may ever appear without one of these two provenances.
No patient-level data is used anywhere — only public HTA documents.

The 6 fixed criteria (do not change these without telling me first):
1. clinical_benefit — comparative effectiveness vs. current standard of care
2. safety — harms, adverse events, tolerability
3. cost_effectiveness — cost per unit of health benefit (e.g., cost/QALY)
4. budget_impact — net effect on payer budget if adopted
5. equity_access — effect on underserved or high-need populations
6. feasibility — practicality of delivering/implementing the technology

Stack: Python/FastAPI backend, Claude API (model: claude-sonnet-4-6) for evidence
extraction, pyDecision (open-source PyPI package) for the MCDA scoring math, React
frontend, SQLite for the audit log. A working reference UI prototype already exists
(evidencescope.jsx) with a specific visual design (paper background, serif headers,
teal = AI-suggested / amber = human-overridden) — preserve that design when we build
the real frontend on Day 6.

Current phase: see the sprint plan. Always tell me your plan before writing code for
a new feature, and flag anything you're uncertain about rather than guessing silently.
