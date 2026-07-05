from pydantic import BaseModel
from typing import Literal

CRITERIA = [
    "clinical_benefit",
    "safety",
    "cost_effectiveness",
    "budget_impact",
    "equity_access",
    "feasibility",
]

# Full definitions used in prompts and UI
CRITERIA_DEFS = [
    {
        "key": "clinical_benefit",
        "label": "Clinical Benefit",
        "definition": "Comparative effectiveness vs. current standard of care",
    },
    {
        "key": "safety",
        "label": "Safety",
        "definition": "Harms, adverse events, tolerability",
    },
    {
        "key": "cost_effectiveness",
        "label": "Cost-Effectiveness",
        "definition": "Cost per unit of health benefit (e.g., cost/QALY)",
    },
    {
        "key": "budget_impact",
        "label": "Budget Impact",
        "definition": "Net effect on payer budget if adopted",
    },
    {
        "key": "equity_access",
        "label": "Equity & Access",
        "definition": "Effect on underserved or high-need populations",
    },
    {
        "key": "feasibility",
        "label": "Feasibility",
        "definition": "Practicality of delivering/implementing the technology",
    },
]

CriterionName = Literal[
    "clinical_benefit",
    "safety",
    "cost_effectiveness",
    "budget_impact",
    "equity_access",
    "feasibility",
]


class PageChunk(BaseModel):
    page_number: int
    text: str


class CriterionScore(BaseModel):
    criterion: CriterionName
    score: int  # 1-9
    evidence_text: str
    page_number: int
    provenance: Literal["ai_extracted", "human_override"]
