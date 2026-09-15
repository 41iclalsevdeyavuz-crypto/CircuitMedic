from pathlib import Path

from app.services.diagnostic_engine import DiagnosticEngine


SAMPLE = Path(
    "data/sample_projects/obstacle_robot/broken_robot.ino"
)


def test_broken_robot_produces_grounded_diagnoses():
    report = DiagnosticEngine().analyze(
        SAMPLE.read_text(encoding="utf-8"),
        "Robot misses obstacles",
        SAMPLE.name,
    )

    assert len(report.issues) == 3

    assert any(
        "Trigger pulse" in issue.title
        for issue in report.issues
    )

    assert any(
        "timeout" in issue.title
        for issue in report.issues
    )

    assert all(
        issue.evidence is not None
        for issue in report.issues
    )

    assert all(
        issue.evidence.text
        for issue in report.issues
        if issue.evidence is not None
    )

    assert all(
        issue.code_location.startswith(
            "broken_robot.ino:"
        )
        for issue in report.issues
    )


def test_no_echo_issue_uses_arduino_pulsein_evidence():
    report = DiagnosticEngine().analyze(
        SAMPLE.read_text(encoding="utf-8"),
        "Robot misses obstacles",
        SAMPLE.name,
    )

    no_echo_issue = next(
        issue
        for issue in report.issues
        if issue.title
        == "No-echo result is used as a valid distance"
    )

    assert no_echo_issue.evidence is not None

    assert (
        no_echo_issue.evidence.source
        == "arduino_pulsein.md"
    )

    evidence_text = (
        no_echo_issue.evidence.text.lower()
    )

    assert "returns 0" in evidence_text
    assert "timeout" in evidence_text