from app.services.llm_service import AIExplanation, LLMService


def test_rejects_unknown_evidence_id():
    service = LLMService()

    explanation = AIExplanation(
        possible_cause="Example cause",
        symptom_relationship="Example relationship",
        technical_explanation="Example explanation",
        recommended_fix="Example fix",
        evidence_ids=[
            "hc_sr04_original_p1_c1",
            "fake_evidence_999",
        ],
        uncertainty="Example uncertainty",
    )

    valid_evidence_ids = [
        "hc_sr04_original_p1_c1",
        "arduino_pulsein_c1",
    ]

    is_valid = service._validate_evidence_ids(
        explanation,
        valid_evidence_ids,
    )

    assert is_valid is False

from types import SimpleNamespace


class FakeResponses:
    def parse(self, **kwargs):
        fake_explanation = AIExplanation(
            possible_cause="A fabricated explanation",
            symptom_relationship="Example relationship",
            technical_explanation="Example explanation",
            recommended_fix="Example fix",
            evidence_ids=[
                "fake_evidence_999",
            ],
            uncertainty="Example uncertainty",
        )

        return SimpleNamespace(
            output_parsed=fake_explanation
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_explain_rejects_unknown_evidence_id():
    from app.services.diagnostic_engine import DiagnosticEngine

    firmware = """
const int trigPin = 9;
const int echoPin = 10;

void loop() {
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(4);
    digitalWrite(trigPin, LOW);

    long duration = pulseIn(echoPin, HIGH);
    float distanceCm = duration / 58.0;
}
"""

    report = DiagnosticEngine().analyze(
        firmware,
        "Robot occasionally misses obstacles.",
        "test_robot.ino",
    )

    assert report.issues

    service = LLMService()

    # Avoid a real API call.
    service.client = FakeClient()

    explanation = service.explain(
        report,
        firmware,
    )

    # A fabricated evidence ID must invalidate
    # the complete AI explanation.
    assert explanation is None