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

    Supported safe patterns include:

        if (duration == 0) {
            return;
        }

        if (duration == 0) return;

        if (duration != 0) {
            distance = duration / 58.0;
        }

    A check is not considered safe if execution can continue
    into an unguarded distance conversion.

    This is intentionally conservative and does not attempt
    to fully parse arbitrary C++ control flow.
    """
    escaped = re.escape(variable)

    following = lines[
        pulse_line_index + 1:
        pulse_line_index + 16
    ]

    text = "\n".join(following)

    conversion_pattern = re.compile(
        rf"\b{escaped}\b\s*/|"
        rf"\b{escaped}\b\s*\*"
    )

    first_conversion = conversion_pattern.search(
        text
    )

    # Pattern 1:
    # if (duration == 0) return;
    # if (duration <= 0) return;
    # if (!duration) return;
    inline_terminating_guard = re.search(
        (
            rf"if\s*\(\s*(?:"
            rf"{escaped}\s*==\s*0|"
            rf"{escaped}\s*<=\s*0|"
            rf"!\s*{escaped}"
            rf")\s*\)"
            rf"\s*"
            rf"(?:return\b[^;]*;|continue\s*;|break\s*;)"
        ),
        text,
        re.DOTALL,
    )

    if inline_terminating_guard:
        if (
            first_conversion is None
            or inline_terminating_guard.start()
            < first_conversion.start()
        ):
            return True

    # Pattern 2:
    # if (duration == 0) {
    #     ...
    #     return;
    # }
    zero_guard = re.search(
        (
            rf"if\s*\(\s*(?:"
            rf"{escaped}\s*==\s*0|"
            rf"{escaped}\s*<=\s*0|"
            rf"!\s*{escaped}"
            rf")\s*\)"
            rf"\s*\{{"
        ),
        text,
    )

    if zero_guard:
        open_brace = text.find(
            "{",
            zero_guard.start(),
        )

        if open_brace != -1:
            depth = 0
            close_brace = None

            for pos in range(
                open_brace,
                len(text),
            ):
                if text[pos] == "{":
                    depth += 1

                elif text[pos] == "}":
                    depth -= 1

                    if depth == 0:
                        close_brace = pos
                        break

            if close_brace is not None:
                guard_body = text[
                    open_brace + 1:
                    close_brace
                ]

                terminates_flow = re.search(
                    r"\breturn\b[^;]*;|"
                    r"\bcontinue\s*;|"
                    r"\bbreak\s*;",
                    guard_body,
                )

                if terminates_flow:
                    if (
                        first_conversion is None
                        or zero_guard.start()
                        < first_conversion.start()
                    ):
                        return True

    # Pattern 3:
    # if (duration != 0) {
    #     distance = duration / 58.0;
    # }
    #
    # The conversion itself must be inside the positive guard.
    positive_guard = re.search(
        (
            rf"if\s*\(\s*"
            rf"{escaped}\s*(?:!=|>)\s*0"
            rf"\s*\)"
            rf"\s*\{{"
        ),
        text,
    )

    if positive_guard:
        open_brace = text.find(
            "{",
            positive_guard.start(),
        )

        if open_brace != -1:
            depth = 0
            close_brace = None

            for pos in range(
                open_brace,
                len(text),
            ):
                if text[pos] == "{":
                    depth += 1

                elif text[pos] == "}":
                    depth -= 1

                    if depth == 0:
                        close_brace = pos
                        break

            if close_brace is not None:
                guard_body = text[
                    open_brace + 1:
                    close_brace
                ]

                guarded_conversion = (
                    conversion_pattern.search(
                        guard_body
                    )
                )

                if guarded_conversion:
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

        # A. Analyze the selected TRIG pin between HIGH and the next LOW.
    # Constant delayMicroseconds() calls in that interval are summed.
    #
    # This supports both:
    #
    # digitalWrite(trigPin, HIGH);
    # delayMicroseconds(4);
    # digitalWrite(trigPin, LOW);
    #
    # and:
    #
    # digitalWrite(trigPin, HIGH); delayMicroseconds(4); digitalWrite(trigPin, LOW);

    trigger_high_pattern = re.compile(
        rf"digitalWrite\s*\(\s*{trig_escaped}\s*,\s*HIGH\s*\)\s*;"
    )

    trigger_low_pattern = re.compile(
        rf"digitalWrite\s*\(\s*{trig_escaped}\s*,\s*LOW\s*\)\s*;"
    )

    delay_pattern = re.compile(
        r"delayMicroseconds\s*\(\s*([^)]+?)\s*\)"
    )

    # Search the cleaned source as one string so statements on the
    # same physical line are handled correctly.
    for high_match in trigger_high_pattern.finditer(cleaned):
        low_match = trigger_low_pattern.search(
            cleaned,
            high_match.end(),
        )

        if low_match is None:
            continue

        between = cleaned[
            high_match.end():
            low_match.start()
        ]

        delays = list(
            delay_pattern.finditer(between)
        )

        if not delays:
            # Without an explicit constant delay we do not make
            # a definite timing claim.
            continue

        total_delay = 0
        all_constant = True

        for delay_match in delays:
            argument = delay_match.group(1).strip()

            if not argument.isdigit():
                all_constant = False
                break

            total_delay += int(argument)

        if not all_constant:
            # Variable or complex timing requires manual review;
            # do not emit a definite short-pulse diagnosis.
            continue

        if total_delay < 10:
            first_delay = delays[0]

            absolute_delay_position = (
                high_match.end()
                + first_delay.start()
            )

            line_number = (
                cleaned.count(
                    "\n",
                    0,
                    absolute_delay_position,
                )
                + 1
            )

            if len(delays) == 1:
                observed = (
                    f"delayMicroseconds({total_delay})"
                )
            else:
                observed = (
                    f"Total explicit TRIG HIGH delay: "
                    f"{total_delay} microseconds"
                )

            findings.append(
                Finding(
                    "short_trigger_pulse",
                    line_number,
                    observed,
                )
            )

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