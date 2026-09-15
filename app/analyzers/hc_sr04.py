"""Focused, conservative checks for Arduino HC-SR04 firmware.

This is a small statement reader, not a C++ compiler. It recognizes ordinary
calls, literal/immutable integer delays, and simple zero guards. It deliberately
does not infer timing through branches, loops, or arbitrary function calls.
"""
from dataclasses import dataclass, field
import ast
import re


@dataclass(frozen=True)
class Finding:
    kind: str
    line: int
    observed: str


def _strip_comments_keep_lines(source: str) -> str:
    """Mask comments AND C++ literals without changing offsets or line numbers."""
    pattern = re.compile(
        r'(?P<raw>(?:u8|u|U|L)?R"(?P<delimiter>[^\s()\\]{0,16})\('
        r'.*?\)(?P=delimiter)")'
        r'|(?P<string>"(?:\\[\s\S]|[^"\\])*(?:"|$))'
        r"|(?P<char>'(?:\\[\s\S]|[^'\\])*(?:'|$))"
        r'|(?P<line>//(?:\\\n|[^\n])*)'
        r'|(?P<block>/\*[\s\S]*?(?:\*/|$))',
        re.DOTALL,
    )
    return pattern.sub(
        lambda match: ''.join('\n' if c == '\n' else ' ' for c in match[0]),
        source,
    )


@dataclass
class _Statement:
    kind: str
    text: str
    start: int
    body: list['_Statement'] = field(default_factory=list)
    otherwise: list['_Statement'] = field(default_factory=list)


def _closing(text: str, start: int, opening: str = '(', closing: str = ')') -> int:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == opening:
            depth += 1
        elif text[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def _statements(source: str, offset: int = 0) -> list[_Statement]:
    """Read statement boundaries and if/else bodies, independent of newlines."""
    def space(index):
        while index < len(source) and source[index].isspace():
            index += 1
        return index

    def one(index):
        index = space(index)
        if index >= len(source):
            return _Statement('simple', '', offset + index), index
        if source[index] == '{':
            end = _closing(source, index, '{', '}')
            return _Statement('block', '', offset + index,
                              _statements(source[index + 1:end], offset + index + 1)), end + 1
        control = re.match(r'(if|while|for|switch)\s*\(', source[index:])
        if control:
            opening = index + control.end() - 1
            end = _closing(source, opening)
            body, after = one(end + 1)
            alternate = []
            next_index = space(after)
            if control[1] == 'if' and re.match(r'else\b', source[next_index:]):
                other, after = one(next_index + 4)
                alternate = other.body if other.kind == 'block' else [other]
            return _Statement(
                control[1], source[opening + 1:end], offset + opening + 1,
                body.body if body.kind == 'block' else [body], alternate,
            ), after
        # Function headers and ordinary statements. Parentheses may contain
        # nested calls or semicolons (e.g. a for header).
        cursor = index
        while cursor < len(source):
            char = source[cursor]
            if char == '(':
                cursor = _closing(source, cursor) + 1
                continue
            if char == '{':
                end = _closing(source, cursor, '{', '}')
                return _Statement('block', source[index:cursor], offset + index,
                                  _statements(source[cursor + 1:end], offset + cursor + 1)), end + 1
            if char in ';}':
                return _Statement('simple', source[index:cursor + (char == ';')],
                                  offset + index), cursor + 1
            cursor += 1
        return _Statement('simple', source[index:], offset + index), cursor

    result = []
    index = 0
    while space(index) < len(source):
        statement, after = one(index)
        if after <= index:
            break
        result.append(statement)
        index = after
    return result


def _calls(text: str, name: str):
    for match in re.finditer(rf'\b{re.escape(name)}\s*\(', text):
        opening = match.end() - 1
        end = _closing(text, opening)
        arguments = text[opening + 1:end]
        # Split only top-level commas, allowing nested timeout expressions.
        args, start, depth = [], 0, 0
        for index, char in enumerate(arguments):
            if char in '([':
                depth += 1
            elif char in ')]':
                depth -= 1
            elif char == ',' and depth == 0:
                args.append(arguments[start:index].strip())
                start = index + 1
        args.append(arguments[start:].strip())
        yield match.start(), end + 1, args


def _integer(expression: str, constants: dict[str, int]) -> int | None:
    """Evaluate a bounded subset of integer expressions without executing code."""
    expression = re.sub(r'\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]+\b', r'\1', expression.strip())
    try:
        node = ast.parse(expression, mode='eval').body
        def value(part):
            if isinstance(part, ast.Constant) and type(part.value) is int:
                return part.value
            if isinstance(part, ast.Name):
                return constants[part.id]
            if isinstance(part, ast.UnaryOp) and isinstance(part.op, (ast.UAdd, ast.USub)):
                number = value(part.operand)
                return -number if isinstance(part.op, ast.USub) else number
            if isinstance(part, ast.BinOp):
                left, right = value(part.left), value(part.right)
                if isinstance(part.op, ast.Add):
                    return left + right
                if isinstance(part.op, ast.Sub):
                    return left - right
                if isinstance(part.op, ast.Mult):
                    return left * right
            raise ValueError('Unsupported integer expression')
        result = value(node)
        return result if abs(result) <= 2**63 - 1 else None
    except (SyntaxError, ValueError, KeyError, TypeError, RecursionError):
        return None


def _learn_constant(text: str, constants: dict[str, int]) -> None:
    # Ordinary declarations shadow outer constants, even if they are mutable.
    declaration = re.match(
        r'\s*(?P<type>(?:(?:const|constexpr|static|unsigned|signed|long|short)\s+)*'
        r'(?:int|long|short|auto|uint\d+_t|size_t))\s+'
        r'(?P<name>\w+)\s*(?:=\s*(?P<value>[^;]+))?\s*;', text,
    )
    if declaration:
        name = declaration['name']
        result = _integer(declaration['value'] or '', constants)
        constants.pop(name, None)
        if re.search(r'\b(?:const|constexpr)\b', declaration['type']) and result is not None:
            constants[name] = result


def _trigger_findings(nodes: list[_Statement], source: str, trig: str,
                      inherited: dict[str, int] | None = None) -> list[Finding]:
    constants = dict(inherited or {})
    findings = []
    # A pulse can only be assessed within a straight-line statement sequence.
    pending = None
    for node in nodes:
        if node.kind != 'simple':
            pending = None
            nested_constants = dict(constants)
            if node.kind == 'block' and '(' in node.text:
                # Parameters shadow globals; never substitute a global delay
                # constant for a runtime parameter with the same name.
                for name in list(nested_constants):
                    if re.search(rf'\b{re.escape(name)}\b', node.text):
                        nested_constants.pop(name)
            findings.extend(_trigger_findings(node.body, source, trig, nested_constants))
            findings.extend(_trigger_findings(node.otherwise, source, trig, constants))
            continue
        _learn_constant(node.text, constants)
        writes = list(_calls(node.text, 'digitalWrite'))
        if writes:
            _, _, args = writes[0]
            if len(args) == 2 and args[0] == trig:
                if args[1] == 'HIGH':
                    pending = {'delay': 0, 'position': None, 'known': True}
                elif args[1] == 'LOW' and pending is not None:
                    if pending['known'] and pending['position'] is not None and pending['delay'] < 10:
                        findings.append(Finding(
                            'short_trigger_pulse',
                            source.count('\n', 0, pending['position']) + 1,
                            f"Total explicit TRIG HIGH delay: {pending['delay']} microseconds",
                        ))
                    pending = None
                else:
                    pending = None
            elif pending is not None:
                pending['known'] = False
            continue
        if pending is None:
            continue
        delays = [(pos, end, args, scale) for name, scale in
                  [('delayMicroseconds', 1), ('delay', 1000)]
                  for pos, end, args in _calls(node.text, name)]
        if delays and re.fullmatch(r'\s*(?:delayMicroseconds|delay)\s*\([\s\S]*\)\s*;', node.text):
            for pos, _, args, scale in delays:
                amount = _integer(args[0], constants) if len(args) == 1 else None
                if amount is None or amount < 0:
                    pending['known'] = False
                else:
                    pending['delay'] += amount * scale
                    if pending['position'] is None:
                        pending['position'] = node.start + pos
        elif node.text.strip():
            # An arbitrary call or computation may change timing or control flow.
            pending['known'] = False
    return findings


# Each state maps a pulse result variable to (call position, known nonzero).
# Branches retain separate states; a conditional return removes only its branch.
def _condition(text: str, variable: str) -> bool | None:
    compact = re.sub(r'\s+', '', text)
    while compact.startswith('(') and _closing(compact, 0) == len(compact) - 1:
        compact = compact[1:-1]
    if compact in {f'{variable}!=0', f'{variable}>0', f'0!={variable}', f'0<{variable}', variable}:
        return True
    if compact in {f'{variable}==0', f'{variable}<=0', f'0=={variable}', f'!{variable}'}:
        return False
    return None


def _refine(state, condition, truth):
    result = dict(state)
    for variable, (position, safe) in state.items():
        nonzero_when_true = _condition(condition, variable)
        if nonzero_when_true is not None:
            nonzero = nonzero_when_true == truth
            if safe and not nonzero:
                return None  # This branch contradicts a known nonzero value.
            result[variable] = (position, nonzero)
    return result


def _merge_states(states):
    unique = {tuple(sorted(state.items())): state for state in states}
    if len(unique) <= 64:
        return list(unique.values())
    # Bound path growth conservatively: retain every origin, forgetting safety.
    origins = {(name, origin) for state in states for name, (origin, _) in state.items()}
    return [{name: (origin, False)} for name, origin in origins]


def _no_echo_findings(nodes: list[_Statement], source: str, echo: str) -> list[Finding]:
    unsafe = set()

    def scoped(sequence, states):
        # Restore shadowed outer variables when leaving a lexical block.
        # Inner pulse results are still checked, but cannot certify an outer
        # measurement or leak into a different function.
        declared = set()
        for statement in sequence:
            if statement.kind == 'simple':
                match = re.match(
                    r'\s*(?:(?:const|constexpr|static|unsigned|signed|long|short)\s+)*'
                    r'(?:int|long|short|float|double|auto|uint\d+_t|size_t)\s+(\w+)\s*(?:=|;)',
                    statement.text,
                )
                if match:
                    declared.add(match[1])
        results = []
        for original in states:
            local = {name: value for name, value in original.items() if name not in declared}
            for state in walk(sequence, [local]):
                for name in declared:
                    state.pop(name, None)
                    if name in original:
                        state[name] = original[name]
                results.append(state)
        return _merge_states(results)

    def check_use(text, state):
        for variable, (origin, safe) in state.items():
            if not safe and re.search(
                rf'\b{re.escape(variable)}\b\s*[/*]|[/*]\s*\b{re.escape(variable)}\b', text
            ):
                unsafe.add((origin, variable))

    def walk(sequence, states):
        for node in sequence:
            if not states:
                break
            if node.kind == 'if':
                branches = []
                for state in states:
                    check_use(node.text, state)
                    for truth, body in [(True, node.body), (False, node.otherwise)]:
                        refined = _refine(state, node.text, truth)
                        if refined is not None:
                            branches.extend(scoped(body, [refined]))
                states = _merge_states(branches)
            elif node.kind in {'while', 'for', 'switch'}:
                for state in states:
                    check_use(node.text, state)
                # Loops may execute zero times. A return/break in their body
                # must never certify the path after the loop as safe.
                states = _merge_states(states + scoped(node.body, [dict(s) for s in states]))
            elif node.kind == 'block':
                # A named function body is independent of other functions.
                if '(' in node.text:
                    walk(node.body, [{}])
                else:
                    states = scoped(node.body, states)
            else:
                next_states = []
                for state in states:
                    current = dict(state)
                    for position, end, args in _calls(node.text, 'pulseIn'):
                        if not args or args[0] != echo:
                            continue
                        assignment = re.search(r'\b(\w+)\s*=\s*$', node.text[:position])
                        if assignment:
                            current[assignment[1]] = (node.start + position, False)
                        elif re.match(r'\s*[/*]', node.text[end:]):
                            unsafe.add((node.start + position, 'pulseIn result'))
                    check_use(node.text, current)
                    # An assignment can invalidate a previously established guard.
                    for variable, (origin, safe) in list(current.items()):
                        assigned = re.search(rf'\b{re.escape(variable)}\s*=(?!=)([^;]+)', node.text)
                        if assigned and not re.match(r'\s*pulseIn\s*\(', assigned[1]):
                            current[variable] = (origin, False)
                    if not re.match(r'\s*(?:return|throw)\b', node.text):
                        next_states.append(current)
                states = _merge_states(next_states)
        return states

    walk(nodes, [{}])
    return [Finding('unchecked_no_echo', source.count('\n', 0, position) + 1, variable)
            for position, variable in sorted(unsafe)]


def analyze_hc_sr04(firmware: str, trig_symbol: str = 'trigPin',
                   echo_symbol: str = 'echoPin') -> list[Finding]:
    cleaned = _strip_comments_keep_lines(firmware)
    # Preprocessor directives are not executable C++. Conditional preprocessing
    # is outside the supported subset; directives must not merge with statements.
    cleaned = re.sub(r'^\s*#[^\n]*', lambda m: re.sub(r'[^\n]', ' ', m[0]),
                     cleaned, flags=re.MULTILINE)
    nodes = _statements(cleaned)
    findings = _trigger_findings(nodes, cleaned, trig_symbol)
    for position, _, args in _calls(cleaned, 'pulseIn'):
        if args and args[0] == echo_symbol and len(args) < 3:
            findings.append(Finding('missing_echo_timeout', cleaned.count('\n', 0, position) + 1,
                                    f"pulseIn({', '.join(args)})"))
    findings.extend(_no_echo_findings(nodes, cleaned, echo_symbol))
    return list({(finding.kind, finding.line): finding for finding in findings}.values())
