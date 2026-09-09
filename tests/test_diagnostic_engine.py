from pathlib import Path
from app.services.diagnostic_engine import DiagnosticEngine

SAMPLE = Path("data/sample_projects/obstacle_robot/broken_robot.ino")
def test_broken_robot_produces_grounded_diagnoses():
    report = DiagnosticEngine().analyze(SAMPLE.read_text(encoding="utf-8"), "Robot misses obstacles", SAMPLE.name)
    assert len(report.issues) == 3
    assert any("Trigger pulse" in issue.title for issue in report.issues)
    assert any("timeout" in issue.title for issue in report.issues)
    assert all(issue.evidence.text for issue in report.issues)
    assert all(issue.code_location.startswith("broken_robot.ino:") for issue in report.issues)
