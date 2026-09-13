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


RULES = {
    "short_trigger_pulse": (
        "HC-SR04 trigger input pulse duration minimum 10 microseconds",
        "Trigger pulse is shorter than the HC-SR04 requirement",
        "high",
        .97,
        "A trigger shorter than the documented minimum may not start a measurement, producing intermittent missed obstacles.",
        "Hold TRIG HIGH for at least 10 microseconds, e.g. delayMicroseconds(10).",
    ),

    "missing_echo_timeout": (
        "Arduino pulseIn default timeout optional timeout parameter",
        "Echo measurement relies on the default pulseIn timeout",
        "high",
        .92,
        "pulseIn() without an explicit timeout uses Arduino's default timeout, which can be much longer than an HC-SR04 measurement cycle and may stall a real-time control loop.",
        "Use pulseIn(echoPin, HIGH, 30000) and treat 0 as no echo.",
    ),

    "unchecked_no_echo": (
        "HC-SR04 no echo unavailable reading echo return",
        "No-echo result is used as a valid distance",
        "medium",
        .89,
        "A zero duration signals a timeout or no echo, not an obstacle at zero centimetres.",
        "Check duration == 0 before converting the value to distance and enter a safe fallback state.",
    ),
}


class DiagnosticEngine:
    def __init__(
        self,
        knowledge_path: str | Path = DEFAULT_KNOWLEDGE,
    ):
        self.retriever = DatasheetRetriever.from_json(
            knowledge_path
        )

        self.arduino_retriever = DatasheetRetriever.from_markdown(
            ARDUINO_PULSEIN_KNOWLEDGE
        )

    def _diagnosis(
        self,
        finding: Finding,
        filename: str,
    ) -> Diagnosis:
        (
            query,
            title,
            severity,
            confidence,
            explanation,
            fix,
        ) = RULES[finding.kind]

        if finding.kind == "missing_echo_timeout":
            result = self.arduino_retriever.search(
                query,
                1,
            )[0]
        else:
            result = self.retriever.search(
                query,
                1,
            )[0]

        return Diagnosis(
            title=title,
            severity=severity,
            confidence=confidence,
            code_location=f"{filename}:{finding.line}",
            explanation=explanation,
            suggested_fix=fix,
            evidence=Evidence(
                source=result.chunk.source,
                page=result.chunk.page,
                chunk_id=result.chunk.chunk_id,
                section=result.chunk.section,
                text=result.chunk.text,
                score=round(result.score, 3),
            ),
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