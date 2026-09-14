from pathlib import Path

from app.analyzers.hc_sr04 import Finding, analyze_hc_sr04
from app.models import Diagnosis, DiagnosticReport, Evidence
from app.rag.retriever import DatasheetRetriever


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_KNOWLEDGE = (
    ROOT
    / "data"
    / "datasheets"
    / "hc_sr04_chunks.json"
)

ARDUINO_PULSEIN_KNOWLEDGE = (
    ROOT
    / "data"
    / "datasheets"
    / "arduino_pulsein.md"
)

HC_SR04_SOURCE_URL = (
    "https://cdn.sparkfun.com/datasheets/"
    "Sensors/Proximity/HCSR04.pdf"
)

ARDUINO_PULSEIN_SOURCE_URL = (
    "https://docs.arduino.cc/language-reference/"
    "en/functions/advanced-io/pulseIn/"
)


RULES = {
    "short_trigger_pulse": {
        "query": (
            "HC-SR04 trigger pulse minimum duration "
            "10 microseconds requirement"
        ),
        "title": (
            "Trigger pulse is shorter than "
            "the HC-SR04 requirement"
        ),
        "severity": "high",
        "assessment": "direct_rule_match",
        "requirement": (
            "The HC-SR04 requires the TRIG input "
            "to be held HIGH for at least 10 microseconds."
        ),
        "mismatch": (
            "The observed trigger delay is shorter "
            "than the documented minimum."
        ),
        "fix": (
            "Hold TRIG HIGH for at least 10 microseconds, "
            "for example delayMicroseconds(10)."
        ),
        "source_url": HC_SR04_SOURCE_URL,
    },

    "missing_echo_timeout": {
        "query": (
            "Arduino pulseIn optional timeout "
            "default timeout behavior"
        ),
        "title": (
            "Echo measurement relies on "
            "the default pulseIn timeout"
        ),
        "severity": "high",
        "assessment": "direct_rule_match",
        "requirement": (
            "Arduino pulseIn supports an explicit timeout. "
            "For a responsive control loop, the waiting time "
            "should be deliberately bounded."
        ),
        "mismatch": (
            "The pulseIn call does not provide an explicit "
            "timeout, so the control loop relies on the "
            "default behavior."
        ),
        "fix": (
            "Use pulseIn(echoPin, HIGH, 30000) "
            "and treat 0 as no echo."
        ),
        "source_url": ARDUINO_PULSEIN_SOURCE_URL,
    },

    "unchecked_no_echo": {
        "query": (
            "HC-SR04 no echo unavailable reading "
            "invalid zero distance"
        ),
        "title": (
            "No-echo result is used as a valid distance"
        ),
        "severity": "medium",
        "assessment": "possible_issue",
        "requirement": (
            "A missing echo should be treated as an "
            "unavailable measurement rather than as a "
            "valid zero-centimetre distance."
        ),
        "mismatch": (
            "The measured duration can be used in the "
            "distance calculation without first handling "
            "the no-echo case."
        ),
        "fix": (
            "Check duration == 0 before converting the "
            "value to distance and enter a safe fallback state."
        ),
        "source_url": HC_SR04_SOURCE_URL,
    },
}


class DiagnosticEngine:
    def __init__(
        self,
        knowledge_path: str | Path = DEFAULT_KNOWLEDGE,
    ):
        self.retriever = DatasheetRetriever.from_json(
            knowledge_path
        )

        self.arduino_retriever = (
            DatasheetRetriever.from_markdown(
                ARDUINO_PULSEIN_KNOWLEDGE
            )
        )

    def _retrieve_evidence(
        self,
        finding: Finding,
        query: str,
        source_url: str,
    ) -> tuple[Evidence | None, str | None]:

        if finding.kind == "missing_echo_timeout":
            results = self.arduino_retriever.search(
                query,
                1,
            )
        else:
            results = self.retriever.search(
                query,
                1,
            )

        if not results:
            return (
                None,
                (
                    "No sufficiently relevant document evidence "
                    "was found. Manual review is recommended."
                ),
            )

        result = results[0]

        return (
            Evidence(
                source=result.chunk.source,
                source_url=source_url,
                page=result.chunk.page,
                chunk_id=result.chunk.chunk_id,
                section=result.chunk.section,
                text=result.chunk.text,
                score=round(result.score, 3),
            ),
            None,
        )

    def _diagnosis(
        self,
        finding: Finding,
        filename: str,
    ) -> Diagnosis:

        rule = RULES[finding.kind]

        evidence, evidence_note = self._retrieve_evidence(
            finding,
            rule["query"],
            rule["source_url"],
        )

        assessment = rule["assessment"]

        if evidence is None:
            assessment = "manual_review_required"

        return Diagnosis(
            title=rule["title"],
            severity=rule["severity"],
            assessment=assessment,
            code_location=f"{filename}:{finding.line}",
            observed_condition=finding.observed,
            documented_requirement=rule["requirement"],
            mismatch=rule["mismatch"],
            suggested_fix=rule["fix"],
            evidence=evidence,
            evidence_note=evidence_note,
        )

    def analyze(
        self,
        firmware: str,
        symptom: str,
        filename: str = "firmware.ino",
        trig_symbol: str = "trigPin",
        echo_symbol: str = "echoPin",
    ) -> DiagnosticReport:

        issues = [
            self._diagnosis(
                finding,
                filename,
            )
            for finding in analyze_hc_sr04(
                firmware,
                trig_symbol=trig_symbol,
                echo_symbol=echo_symbol,
            )
        ]

        return DiagnosticReport(
            board="Arduino Uno",
            components=["HC-SR04"],
            symptom=symptom,
            issues=issues,
        )