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