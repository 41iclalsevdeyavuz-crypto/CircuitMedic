from pathlib import Path
import json
import sys

import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.diagnostic_engine import DiagnosticEngine
from app.services.llm_service import LLMService


ROOT = Path(__file__).resolve().parents[1]

BROKEN_SAMPLE = (
    ROOT
    / "data"
    / "sample_projects"
    / "obstacle_robot"
    / "broken_robot.ino"
)

FIXED_SAMPLE = (
    ROOT
    / "data"
    / "sample_projects"
    / "obstacle_robot"
    / "fixed_robot.ino"
)


st.set_page_config(
    page_title="CircuitMedic",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 CircuitMedic")
st.caption(
    "Evidence-grounded debugging for Arduino + HC-SR04 firmware"
)


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def safe_decode_uploaded_file(uploaded_file) -> str | None:
    try:
        raw = uploaded_file.getvalue()

        if not raw:
            st.error(
                "The uploaded file is empty. "
                "Please choose a firmware file containing code."
            )
            return None

        return raw.decode("utf-8")

    except UnicodeDecodeError:
        st.error(
            "The uploaded file could not be read as UTF-8 text. "
            "Please upload a readable .ino, .cpp, or .h source file."
        )
        return None


if "firmware" not in st.session_state:
    st.session_state.firmware = load_text_file(
        BROKEN_SAMPLE
    )

if "loaded_source" not in st.session_state:
    st.session_state.loaded_source = "broken_robot.ino"

if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None

if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0

with st.sidebar:
    st.subheader("Hardware context")

    st.selectbox(
        "Board",
        ["Arduino Uno"],
        disabled=True,
    )

    st.selectbox(
        "Supported component",
        ["HC-SR04"],
        disabled=True,
    )

    trig_symbol = st.text_input(
        "TRIG pin symbol",
        value="trigPin",
        help=(
            "Variable name used for the HC-SR04 "
            "TRIG pin in the firmware."
        ),
    )

    echo_symbol = st.text_input(
        "ECHO pin symbol",
        value="echoPin",
        help=(
            "Variable name used for the HC-SR04 "
            "ECHO pin in the firmware."
        ),
    )

    st.divider()

    st.subheader("Demo examples")

    load_broken = st.button(
        "Load broken example",
        use_container_width=True,
    )

    load_fixed = st.button(
        "Load fixed example",
        use_container_width=True,
    )


if load_broken:
    st.session_state.firmware = load_text_file(
        BROKEN_SAMPLE
    )
    st.session_state.loaded_source = "broken_robot.ino"
    st.session_state.last_uploaded_name = None
    st.session_state.uploader_version += 1
    st.rerun()


if load_fixed:
    st.session_state.firmware = load_text_file(
        FIXED_SAMPLE
    )
    st.session_state.loaded_source = "fixed_robot.ino"
    st.session_state.last_uploaded_name = None
    st.session_state.uploader_version += 1
    st.rerun()


uploaded = st.file_uploader(
    "Upload firmware",
    type=["ino", "cpp", "h"],
    key=f"firmware_uploader_{st.session_state.uploader_version}",
)


if uploaded is not None:
    if uploaded.name != st.session_state.last_uploaded_name:
        decoded = safe_decode_uploaded_file(
            uploaded
        )

        if decoded is not None:
            st.session_state.firmware = decoded
            st.session_state.loaded_source = uploaded.name
            st.session_state.last_uploaded_name = uploaded.name


st.caption(
    f"Current source: {st.session_state.loaded_source}"
)


firmware = st.text_area(
    "Firmware",
    key="firmware",
    height=380,
)


symptom = st.text_input(
    "Observed symptom",
    (
        "My obstacle avoidance robot occasionally "
        "fails to detect objects and crashes."
    ),
)


analyze_clicked = st.button(
    "Analyze firmware",
    type="primary",
    use_container_width=True,
)


if analyze_clicked:
    if not firmware.strip():
        st.error(
            "The firmware editor is empty. "
            "Load an example, upload a file, or paste code before analyzing."
        )

    else:
        with st.spinner(
            "Analyzing firmware and retrieving technical evidence..."
        ):
            report = DiagnosticEngine().analyze(
                firmware,
                symptom,
                st.session_state.loaded_source,
                trig_symbol=trig_symbol,
                echo_symbol=echo_symbol,
            )

            llm_service = LLMService()

            ai_explanation = llm_service.explain(
                report,
                firmware,
            )

            if ai_explanation is not None:
                report.ai_explanation = ai_explanation

        if not report.issues:
            st.success(
                "No issues were found within the currently supported HC-SR04 checks."
            )

        else:
            st.subheader(
                f"Analysis complete — {len(report.issues)} issues"
            )

            assessment_labels = {
                "direct_rule_match": "Direct rule match",
                "possible_issue": "Possible issue",
                "manual_review_required": "Manual review required",
            }

            firmware_lines = firmware.splitlines()

            for issue in report.issues:
                icon = {
                    "high": "🔴",
                    "medium": "🟠",
                    "low": "🟡",
                }[issue.severity]

                with st.expander(
                    (
                        f"{icon} {issue.severity.upper()} "
                        f"· {issue.title}"
                    ),
                    expanded=True,
                ):
                    left, right = st.columns(2)

                    left.metric(
                        "Assessment",
                        assessment_labels[
                            issue.assessment
                        ],
                    )

                    right.metric(
                        "Location",
                        issue.code_location,
                    )

                    line_number = None

                    try:
                        line_number = int(
                            issue.code_location.rsplit(
                                ":",
                                1,
                            )[1]
                        )
                    except (
                        ValueError,
                        IndexError,
                    ):
                        pass

                    if (
                        line_number is not None
                        and 1 <= line_number <= len(firmware_lines)
                    ):
                        st.markdown(
                            "**Problematic code line**"
                        )

                        st.code(
                            firmware_lines[
                                line_number - 1
                            ],
                            language="cpp",
                        )

                    st.markdown(
                        "**Observed condition**"
                    )

                    st.code(
                        issue.observed_condition,
                        language=None,
                    )

                    st.markdown(
                        "**Documented requirement**"
                    )

                    st.write(
                        issue.documented_requirement
                    )

                    st.markdown(
                        "**Why this is a mismatch**"
                    )

                    st.write(
                        issue.mismatch
                    )

                    st.markdown(
                        "**Suggested fix**"
                    )

                    st.code(
                        issue.suggested_fix,
                        language=None,
                    )

                    st.markdown(
                        "**Document evidence**"
                    )

                    if issue.evidence is None:
                        st.warning(
                            issue.evidence_note
                            or (
                                "No sufficiently relevant "
                                "document evidence was found."
                            )
                        )

                    else:
                        st.info(
                            issue.evidence.text
                        )

                        source_parts = [
                            (
                                "Source: "
                                f"{issue.evidence.source}"
                            )
                        ]

                        if issue.evidence.page is not None:
                            source_parts.append(
                                (
                                    "page "
                                    f"{issue.evidence.page}"
                                )
                            )

                        if issue.evidence.chunk_id:
                            source_parts.append(
                                (
                                    "chunk "
                                    f"{issue.evidence.chunk_id}"
                                )
                            )

                        source_parts.append(
                            (
                                "retrieval similarity "
                                f"{issue.evidence.score:.3f}"
                            )
                        )

                        st.caption(
                            " · ".join(source_parts)
                        )

                        if issue.evidence.source_url:
                            st.link_button(
                                "Open source document",
                                issue.evidence.source_url,
                            )

                    st.caption(
                        (
                            "Retrieval similarity measures how "
                            "closely the document passage matches "
                            "the search query. It is not the "
                            "probability that the diagnosis is correct."
                        )
                    )

            st.divider()

            if report.ai_explanation is not None:
                st.subheader(
                    "🤖 AI Debugging Explanation"
                )

                ai = report.ai_explanation

                st.markdown(
                    "### Possible cause"
                )
                st.write(
                    ai.possible_cause
                )

                st.markdown(
                    "### Relationship to the symptom"
                )
                st.write(
                    ai.symptom_relationship
                )

                st.markdown(
                    "### Technical explanation"
                )
                st.write(
                    ai.technical_explanation
                )

                st.markdown(
                    "### Recommended fix"
                )
                st.write(
                    ai.recommended_fix
                )

                st.markdown(
                    "### Evidence used"
                )

                if ai.evidence_ids:
                    for evidence_id in ai.evidence_ids:
                        st.code(
                            evidence_id,
                            language=None,
                        )

                else:
                    st.info(
                        "The AI explanation did not cite "
                        "any document evidence."
                    )

                st.markdown(
                    "### Uncertainty / additional checks"
                )

                st.write(
                    ai.uncertainty
                )

            else:
                st.info(
                    "AI explanation could not be generated. "
                    "The rule-based diagnostic report above "
                    "is still valid and available."
                )

        report_json = report.model_dump_json(
            indent=2
        )

        st.download_button(
            label="Download JSON report",
            data=report_json,
            file_name="circuitmedic_report.json",
            mime="application/json",
            use_container_width=True,
        )