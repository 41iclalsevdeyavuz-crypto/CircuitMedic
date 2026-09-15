import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from app.models import DiagnosticReport


load_dotenv()


class AIExplanation(BaseModel):
    possible_cause: str
    symptom_relationship: str
    technical_explanation: str
    recommended_fix: str
    evidence_ids: list[str] = Field(
        default_factory=list
    )
    uncertainty: str


class LLMService:
    def __init__(self):
        self.api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-5.6-luna",
        )

        self.client = None

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=25.0,
                max_retries=1,
            )

    def _collect_evidence_ids(
        self,
        report: DiagnosticReport,
    ) -> list[str]:
        evidence_ids = []

        for issue in report.issues:
            if (
                issue.evidence is not None
                and issue.evidence.chunk_id
            ):
                evidence_ids.append(
                    issue.evidence.chunk_id
                )

        return evidence_ids

    def _validate_evidence_ids(
        self,
        explanation: AIExplanation,
        valid_evidence_ids: list[str],
    ) -> bool:
        """
        Reject the complete AI explanation if it cites
        evidence that was not supplied to the model.

        A valid ID does not prove that every generated
        sentence is supported by that evidence, but this
        prevents fabricated evidence identifiers from
        being silently accepted.
        """

        valid_ids = set(
            valid_evidence_ids
        )

        cited_ids = set(
            explanation.evidence_ids
        )

        return cited_ids.issubset(
            valid_ids
        )

    def explain(
        self,
        report: DiagnosticReport,
        firmware: str,
    ) -> AIExplanation | None:

        if not self.client:
            return None

        # There is nothing useful for the LLM to
        # explain when the deterministic analyzer
        # produced no findings.
        if not report.issues:
            return None

        evidence_ids = self._collect_evidence_ids(
            report
        )

        issues_data = []

        for issue in report.issues:
            evidence = None

            if issue.evidence is not None:
                evidence = {
                    "chunk_id": (
                        issue.evidence.chunk_id
                    ),
                    "source": (
                        issue.evidence.source
                    ),
                    "page": (
                        issue.evidence.page
                    ),
                    "section": (
                        issue.evidence.section
                    ),
                    "text": (
                        issue.evidence.text
                    ),
                }

            issues_data.append(
                {
                    "title": issue.title,
                    "severity": issue.severity,
                    "assessment": issue.assessment,
                    "code_location": (
                        issue.code_location
                    ),
                    "observed_condition": (
                        issue.observed_condition
                    ),
                    "documented_requirement": (
                        issue.documented_requirement
                    ),
                    "mismatch": issue.mismatch,
                    "suggested_fix": (
                        issue.suggested_fix
                    ),
                    "evidence": evidence,
                }
            )

        prompt = f"""
You are the AI explanation layer of CircuitMedic,
an evidence-grounded embedded firmware debugging tool.

Your job is NOT to invent new findings.

Use only the provided:
- user symptom
- board and component information
- firmware
- analyzer findings
- retrieved document evidence

Explain the existing findings clearly.

USER SYMPTOM:
{report.symptom}

BOARD:
{report.board}

COMPONENTS:
{", ".join(report.components)}

FIRMWARE:
{firmware}

ANALYZER FINDINGS:
{issues_data}

AVAILABLE EVIDENCE IDS:
{evidence_ids}

Rules:

1. Do not invent evidence.
2. Do not cite an evidence ID that is not in AVAILABLE EVIDENCE IDS.
3. If the evidence is insufficient, explicitly say so.
4. Distinguish between a confirmed rule match and a possible issue.
5. Explain how the findings relate to the user's symptom.
6. Recommend fixes only when supported by the analyzer findings or provided evidence.
7. Return concise but technically useful explanations.
8. evidence_ids must contain only IDs from AVAILABLE EVIDENCE IDS.
"""

        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful embedded "
                            "systems debugging assistant. "
                            "You must ground every claim "
                            "in the supplied analyzer "
                            "findings and evidence."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                text_format=AIExplanation,
            )

            explanation = response.output_parsed

            if explanation is None:
                return None

            # Fail closed:
            # Never silently remove fabricated evidence IDs.
            # If even one cited ID was not supplied by the
            # retrieval layer, reject the whole explanation.
            if not self._validate_evidence_ids(
                explanation,
                evidence_ids,
            ):
                print(
                    "LLM VALIDATION ERROR: "
                    "AI explanation cited an "
                    "unknown evidence ID."
                )
                return None

            return explanation

        except Exception as exc:
            print(
                "LLM ERROR:",
                repr(exc),
            )
            return None