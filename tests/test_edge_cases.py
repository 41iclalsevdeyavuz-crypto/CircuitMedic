from pathlib import Path

from app.analyzers.hc_sr04 import analyze_hc_sr04
from app.services.diagnostic_engine import DiagnosticEngine


BROKEN_SAMPLE = Path(
    "data/sample_projects/obstacle_robot/broken_robot.ino"
)

FIXED_SAMPLE = Path(
    "data/sample_projects/obstacle_robot/fixed_robot.ino"
)


def test_broken_robot_reports_supported_issues():
    report = DiagnosticEngine().analyze(
        BROKEN_SAMPLE.read_text(encoding="utf-8"),
        "Robot misses obstacles",
        BROKEN_SAMPLE.name,
    )

    assert len(report.issues) == 3

    locations = {
        issue.code_location
        for issue in report.issues
    }

    assert any(
        location.startswith("broken_robot.ino:")
        for location in locations
    )


def test_fixed_robot_removes_supported_issues():
    report = DiagnosticEngine().analyze(
        FIXED_SAMPLE.read_text(encoding="utf-8"),
        "Robot works normally",
        FIXED_SAMPLE.name,
    )

    assert report.issues == []


def test_led_only_code_does_not_trigger_hcsr04_warning():
    firmware = """
const int ledPin = 13;

void setup() {
  pinMode(ledPin, OUTPUT);
}

void loop() {
  digitalWrite(ledPin, HIGH);
  delayMicroseconds(2);
  digitalWrite(ledPin, LOW);
}
"""

    findings = analyze_hc_sr04(
        firmware,
        trig_symbol="trigPin",
        echo_symbol="echoPin",
    )

    assert findings == []


def test_commented_out_pulsein_is_ignored():
    firmware = """
const int echoPin = 10;

void loop() {
  // long duration = pulseIn(echoPin, HIGH);
}
"""

    findings = analyze_hc_sr04(
        firmware,
        trig_symbol="trigPin",
        echo_symbol="echoPin",
    )

    assert findings == []


def test_supported_valid_no_echo_guard_does_not_warn():
    firmware = """
const int echoPin = 10;

void loop() {
  long duration = pulseIn(echoPin, HIGH, 30000);

  if (duration != 0) {
    float distanceCm = duration / 58.0;
  }
}
"""

    findings = analyze_hc_sr04(
        firmware,
        trig_symbol="trigPin",
        echo_symbol="echoPin",
    )

    kinds = {
        finding.kind
        for finding in findings
    }

    assert "unchecked_no_echo" not in kinds
    assert "missing_echo_timeout" not in kinds