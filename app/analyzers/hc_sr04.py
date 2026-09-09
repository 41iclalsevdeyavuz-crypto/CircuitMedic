from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Finding:
    kind: str
    line: int
    observed: str

def analyze_hc_sr04(firmware: str) -> list[Finding]:
    findings = []
    lines = firmware.splitlines()
    for index, line in enumerate(lines):
        if re.search(r"digitalWrite\s*\([^,]+,\s*HIGH\s*\)\s*;", line):
            for offset, next_line in enumerate(lines[index + 1:index + 5], start=1):
                match = re.search(r"delayMicroseconds\s*\(\s*(\d+)\s*\)", next_line)
                if match:
                    if int(match.group(1)) < 10:
                        findings.append(Finding("short_trigger_pulse", index + offset + 1, match.group(0)))
                    break
        call = re.search(r"pulseIn\s*\(([^)]*)\)", line)
        if call and len(call.group(1).split(",")) < 3:
            findings.append(Finding("missing_echo_timeout", index + 1, call.group(0)))

    for var in re.findall(r"(\w+)\s*=\s*pulseIn\s*\(", firmware):
        guarded = re.search(rf"if\s*\(\s*{re.escape(var)}\s*(?:==|<=|>)\s*0", firmware)
        if not guarded:
            line = next((i for i, value in enumerate(lines, 1) if re.search(rf"\b{re.escape(var)}\s*=\s*pulseIn", value)), 1)
            findings.append(Finding("unchecked_no_echo", line, var))
    return list({(f.kind, f.line): f for f in findings}.values())
