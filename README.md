# EvidenceScope

Evidence-linked MCDA tool for health technology reimbursement review.

Given a health technology assessment (HTA) report (PDF), EvidenceScope extracts evidence
for 6 fixed criteria, suggests a 1-9 score per criterion with a citation back to the source
page, and lets a human review or override every score before computing a weighted total.

Every score is traceable to either extracted evidence or a logged human override.
No patient data is used anywhere.

## Setup

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

## Status

Under active development — July 2026.
