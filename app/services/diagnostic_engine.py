from pathlib import Path
from app.analyzers.hc_sr04 import Finding, analyze_hc_sr04
from app.models import Diagnosis, DiagnosticReport, Evidence
from app.rag.retriever import DatasheetRetriever

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE = ROOT / "data" / "datasheets" / "hc_sr04.md"
RULES = {
    "short_trigger_pulse": ("HC-SR04 trigger input pulse duration minimum 10 microseconds", "Trigger pulse is shorter than the HC-SR04 requirement", "high", .97, "A trigger shorter than the documented minimum may not start a measurement, producing intermittent missed obstacles.", "Hold TRIG HIGH for at least 10 microseconds, e.g. delayMicroseconds(10)."),
    "missing_echo_timeout": ("HC-SR04 echo pulse timeout maximum range no echo", "Echo measurement can block without a timeout", "high", .92, "pulseIn() without an explicit timeout can stall the control loop far longer than a normal measurement.", "Use pulseIn(echoPin, HIGH, 30000) and treat 0 as no echo."),
    "unchecked_no_echo": ("HC-SR04 no echo timeout invalid zero distance", "No-echo result is used as a valid distance", "medium", .89, "A zero duration signals a timeout/no echo, not an obstacle at zero centimetres.", "Check duration == 0 before converting to distance and enter a safe fallback state."),
}

class DiagnosticEngine:
    def __init__(self, knowledge_path: str | Path = DEFAULT_KNOWLEDGE):
        self.retriever = DatasheetRetriever.from_markdown(knowledge_path)

    def _diagnosis(self, finding: Finding, filename: str) -> Diagnosis:
        query, title, severity, confidence, explanation, fix = RULES[finding.kind]
        result = self.retriever.search(query, 1)[0]
        return Diagnosis(title=title, severity=severity, confidence=confidence,
            code_location=f"{filename}:{finding.line}", explanation=explanation, suggested_fix=fix,
            evidence=Evidence(source=result.chunk.source, section=result.chunk.section,
                text=result.chunk.text, score=round(result.score, 3)))

    def analyze(self, firmware: str, symptom: str, filename: str = "firmware.ino") -> DiagnosticReport:
        issues = [self._diagnosis(f, filename) for f in analyze_hc_sr04(firmware)]
        return DiagnosticReport(board="Arduino Uno", components=["HC-SR04"], symptom=symptom, issues=issues)
