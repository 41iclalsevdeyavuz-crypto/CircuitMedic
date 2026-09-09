from typing import Literal
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    source: str
    section: str
    text: str
    score: float = Field(ge=0.0, le=1.0)

class Diagnosis(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"]
    confidence: float = Field(ge=0.0, le=1.0)
    code_location: str
    explanation: str
    suggested_fix: str
    evidence: Evidence

class DiagnosticReport(BaseModel):
    board: str
    components: list[str]
    symptom: str
    issues: list[Diagnosis]
