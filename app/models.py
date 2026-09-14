from typing import Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: str
    source_url: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    section: str | None = None
    text: str
    score: float = Field(
        ge=0.0,
        le=1.0,
    )


class Diagnosis(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"]

    assessment: Literal[
        "direct_rule_match",
        "possible_issue",
        "manual_review_required",
    ]

    code_location: str

    observed_condition: str
    documented_requirement: str
    mismatch: str

    suggested_fix: str

    evidence: Evidence | None = None
    evidence_note: str | None = None


class DiagnosticReport(BaseModel):
    board: str
    components: list[str]
    symptom: str
    issues: list[Diagnosis]