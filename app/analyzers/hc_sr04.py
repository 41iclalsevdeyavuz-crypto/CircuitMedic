from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Finding:
    kind: str
    line: int
    observed: str


def _strip_comments_keep_lines(source: str) -> str:
    """
    Removes // and /* ... */ comments while preserving newline positions.
    This keeps diagnostic line numbers aligned with the original source.
    """
    result = []
    i = 0
    in_block_comment = False

    while i < len(source):
        if in_block_comment:
            if source.startswith("*/", i):
                in_block_comment = False
                result.extend("  ")
                i += 2
            else:
                if source[i] == "\n":
                    result.append("\n")
                else:
                    result.append(" ")
                i += 1
            continue

        if source.startswith("/*", i):
            in_block_comment = True
            result.extend("  ")
            i += 2
            continue

        if source.startswith("//", i):
            while i < len(source) and source[i] != "\n":
                result.append(" ")
                i += 1
            continue

        result.append(source[i])
        i += 1

    return "".join(result)


def _has_valid_no_echo_guard(
    lines: list[str],
    pulse_line_index: int,
    variable: str,
) -> bool:
    """
    Recognizes a few simple no-echo guard styles after pulseIn().

    Supported examples:
        if (duration == 0) return;
        if (duration <= 0) return;
        if (duration != 0) {
            distance = duration / 58.0;
        }

    This is intentionally conservative rather than pretending to fully parse C++.
    """
    escaped = re.escape(variable)

    # Only inspect a small region after the pulseIn assignment.
    following = lines[pulse_line_index + 1:pulse_line_index + 12]
    text = "\n".join(following)

    invalid_guard_patterns = [
        rf"if\s*\(\s*{escaped}\s*==\s*0\s*\)",
        rf"if\s*\(\s*{escaped}\s*<=\s*0\s*\)",
        rf"if\s*\(\s*!\s*{escaped}\s*\)",
    ]

    for pattern in invalid_guard_patterns:
        match = re.search(pattern, text)
        if match:
            # Guard exists before likely distance conversion.
            guard_pos = match.start()
            conversion = re.search(
                rf"\b{escaped}\b\s*/|"
                rf"\b{escaped}\b\s*\*",
                text,
            )
            if conversion is None or guard_pos < conversion.start():
                return True

    positive_guard = re.search(
        rf"if\s*\(\s*{escaped}\s*(?:!=|>)\s*0\s*\)",
        text,
    )

    if positive_guard:
        # Accept a positive guard if duration use follows the guard.
        after_guard = text[positive_guard.end():]
        if re.search(
            rf"\b{escaped}\b\s*/|"
            rf"\b{escaped}\b\s*\*",
            after_guard,
        ):
            return True

    return False


def analyze_hc_sr04(
    firmware: str,
    trig_symbol: str = "trigPin",
    echo_symbol: str = "echoPin",
) -> list[Finding]:
    findings = []

    cleaned = _strip_comments_keep_lines(firmware)
    lines = cleaned.splitlines()

    trig_escaped = re.escape(trig_symbol)
    echo_escaped = re.escape(echo_symbol)

    # A. Only treat HIGH writes to the selected TRIG symbol as trigger pulses.
    for index, line in enumerate(lines):
        if re.search(
            rf"digitalWrite\s*\(\s*{trig_escaped}\s*,\s*HIGH\s*\)\s*;",
            line,
        ):
            for offset, next_line in enumerate(
                lines[index + 1:index + 5],
                start=1,
            ):
                match = re.search(
                    r"delayMicroseconds\s*\(\s*(\d+)\s*\)",
                    next_line,
                )

                if match:
                    if int(match.group(1)) < 10:
                        findings.append(
                            Finding(
                                "short_trigger_pulse",
                                index + offset + 1,
                                match.group(0),
                            )
                        )
                    break

    # B. Ignore commented-out pulseIn() calls.
    # Also limit timeout detection to the configured ECHO symbol.
    for index, line in enumerate(lines):
        call = re.search(
            rf"pulseIn\s*\(\s*{echo_escaped}\s*,([^)]*)\)",
            line,
        )

        if not call:
            continue

        args = [
            arg.strip()
            for arg in f"{echo_symbol},{call.group(1)}".split(",")
        ]

        if len(args) < 3:
            findings.append(
                Finding(
                    "missing_echo_timeout",
                    index + 1,
                    f"pulseIn({', '.join(args)})",
                )
            )

    # C. Check whether pulseIn() results are safely guarded before use.
    assignment_pattern = re.compile(
        rf"\b(\w+)\s*=\s*pulseIn\s*\(\s*{echo_escaped}\s*,"
    )

    for index, line in enumerate(lines):
        assignment = assignment_pattern.search(line)

        if not assignment:
            continue

        variable = assignment.group(1)

        if not _has_valid_no_echo_guard(lines, index, variable):
            findings.append(
                Finding(
                    "unchecked_no_echo",
                    index + 1,
                    variable,
                )
            )

    return list(
        {
            (finding.kind, finding.line): finding
            for finding in findings
        }.values()
    )