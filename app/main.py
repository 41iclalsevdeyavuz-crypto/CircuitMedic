from pathlib import Path
import sys

import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.diagnostic_engine import DiagnosticEngine


SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "sample_projects"
    / "obstacle_robot"
    / "broken_robot.ino"
)

st.set_page_config(
    page_title="CircuitMedic",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 CircuitMedic")
st.caption("Evidence-grounded debugging for Arduino + HC-SR04 firmware")


with st.sidebar:
    st.subheader("Hardware context")

    st.selectbox(
        "Board",
        ["Arduino Uno"],
    )

    st.multiselect(
        "Components",
        ["HC-SR04"],
        default=["HC-SR04"],
    )

    trig_symbol = st.text_input(
        "TRIG pin symbol",
        value="trigPin",
        help="Variable name used for the HC-SR04 TRIG pin in the firmware.",
    )

    echo_symbol = st.text_input(
        "ECHO pin symbol",
        value="echoPin",
        help="Variable name used for the HC-SR04 ECHO pin in the firmware.",
    )

    load_sample = st.button(
        "Load broken robot demo"
    )


if "firmware" not in st.session_state or load_sample:
    st.session_state.firmware = SAMPLE.read_text(
        encoding="utf-8"
    )


uploaded = st.file_uploader(
    "Upload firmware",
    type=["ino", "cpp", "h"],
)


if uploaded:
    st.session_state.firmware = uploaded.getvalue().decode(
        "utf-8"
    )


firmware = st.text_area(
    "Firmware",
    key="firmware",
    height=350,
)


symptom = st.text_input(
    "Observed symptom",
    "My obstacle avoidance robot occasionally fails to detect objects and crashes.",
)


if st.button(
    "Analyze firmware",
    type="primary",
    use_container_width=True,
):
    report = DiagnosticEngine().analyze(
        firmware,
        symptom,
        uploaded.name if uploaded else "broken_robot.ino",
        trig_symbol=trig_symbol,
        echo_symbol=echo_symbol,
    )

    if not report.issues:
        st.success(
            "No supported HC-SR04 timing or timeout issue was detected."
        )

    else:
        st.subheader(
            f"Analysis complete — {len(report.issues)} issues"
        )

        for issue in report.issues:
            icon = {
                "high": "🔴",
                "medium": "🟠",
                "low": "🟡",
            }[issue.severity]

            with st.expander(
                f"{icon} {issue.severity.upper()} · {issue.title}",
                expanded=True,
            ):
                left, right = st.columns(2)

                left.metric(
                    "Confidence",
                    f"{issue.confidence:.0%}",
                )

                right.metric(
                    "Location",
                    issue.code_location,
                )

                st.write(issue.explanation)

                st.markdown("**Suggested fix**")

                st.code(
                    issue.suggested_fix,
                    language=None,
                )

                st.markdown(
                    "**Retrieved evidence**"
                )

                st.info(
                    issue.evidence.text
                )

                source_parts = [
                    f"Source: {issue.evidence.source}"
                ]

                if issue.evidence.page is not None:
                    source_parts.append(
                        f"page {issue.evidence.page}"
                    )

                if issue.evidence.chunk_id:
                    source_parts.append(
                        f"chunk {issue.evidence.chunk_id}"
                    )

                source_parts.append(
                    f"retrieval score {issue.evidence.score:.3f}"
                )

                st.caption(
                    " · ".join(source_parts)
                )