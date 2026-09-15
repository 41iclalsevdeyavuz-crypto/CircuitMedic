"""Regression cases reproduced during the firmware analyzer review.

These tests exercise the real analyzer, without a model download or API key.
They also run with `python -m unittest discover -s tests -p test_analyzer_reliability.py`.
"""
from pathlib import Path
import unittest

from app.analyzers.hc_sr04 import analyze_hc_sr04


class AnalyzerReliabilityTests(unittest.TestCase):
    def kinds(self, source, **kwargs):
        return {finding.kind for finding in analyze_hc_sr04(source, **kwargs)}

    def pulse(self, tail):
        return 'void loop() {\nlong duration = pulseIn(echoPin, HIGH, 30000);\n' + tail + '\n}'

    def test_multiline_call_detects_both_issues_and_source_line(self):
        source = '''void loop() {
long duration = pulseIn(
    echoPin,
    HIGH
);
float distance = duration / 58.0;
}'''
        findings = analyze_hc_sr04(source)
        self.assertEqual({f.kind for f in findings}, {'missing_echo_timeout', 'unchecked_no_echo'})
        self.assertTrue(all(f.line == 2 for f in findings))

    def test_same_line_early_return_is_safe(self):
        source = '''void loop() {
long duration = pulseIn(echoPin, HIGH, 30000); if (duration == 0) return;
float distance = duration / 58.0;
}'''
        self.assertEqual(self.kinds(source), set())

    def test_conditional_return_does_not_protect_every_path(self):
        source = self.pulse('''if (duration == 0) {
    if (emergency) return;
}
float distance = duration / 58.0;''')
        self.assertIn('unchecked_no_echo', self.kinds(source))

    def test_guarded_use_does_not_hide_later_unguarded_use(self):
        source = self.pulse('''if (duration != 0) {
    float safeDistance = duration / 58.0;
}
float unsafeDistance = duration / 58.0;''')
        self.assertIn('unchecked_no_echo', self.kinds(source))

    def test_milliseconds_are_included_in_trigger_duration(self):
        source = '''void loop() {
digitalWrite(trigPin, HIGH);
delay(1);
delayMicroseconds(4);
digitalWrite(trigPin, LOW);
}'''
        self.assertNotIn('short_trigger_pulse', self.kinds(source))

    def test_calls_inside_literals_are_ignored(self):
        for literal in ['"pulseIn(echoPin, HIGH)"',
                        '"quoted \\\" pulseIn(echoPin, HIGH)"',
                        'R"tag(pulseIn(echoPin, HIGH)\n/* text */)tag"',
                        '"https://example.test/pulseIn(echoPin, HIGH)"']:
            with self.subTest(literal=literal):
                self.assertEqual(self.kinds('void loop() { Serial.println(' + literal + '); }'), set())

    def test_const_trigger_delay_is_resolved(self):
        source = '''const int TRIGGER_US = 4;
void loop() {
digitalWrite(trigPin, HIGH);
delayMicroseconds(TRIGGER_US);
digitalWrite(trigPin, LOW);
}'''
        findings = analyze_hc_sr04(source)
        self.assertEqual([f.kind for f in findings], ['short_trigger_pulse'])
        self.assertEqual(findings[0].line, 4)

    def test_constant_expression_and_safe_constant_delay(self):
        for declaration, value, short in [('const int', '2 + 2', True),
                                          ('constexpr unsigned int', '10UL', False)]:
            with self.subTest(value=value):
                code = f'''{declaration} WAIT = {value};
void loop() {{
digitalWrite(trigPin, HIGH); delayMicroseconds(WAIT); digitalWrite(trigPin, LOW);
}}'''
                self.assertEqual('short_trigger_pulse' in self.kinds(code), short)

    def test_mutable_shadow_is_not_treated_as_outer_constant(self):
        code = '''const int WAIT = 4;
void loop() {
int WAIT = readDelay();
digitalWrite(trigPin, HIGH); delayMicroseconds(WAIT); digitalWrite(trigPin, LOW);
}'''
        self.assertNotIn('short_trigger_pulse', self.kinds(code))

    def test_branch_delays_are_not_added_as_if_both_execute(self):
        code = '''void loop() {
digitalWrite(trigPin, HIGH);
if (mode) delayMicroseconds(4); else delayMicroseconds(4);
digitalWrite(trigPin, LOW);
}'''
        self.assertNotIn('short_trigger_pulse', self.kinds(code))

    def test_function_parameter_shadows_global_delay_constant(self):
        code = '''const int WAIT = 4;
void measure(int WAIT) {
digitalWrite(trigPin, HIGH); delayMicroseconds(WAIT); digitalWrite(trigPin, LOW);
}'''
        self.assertNotIn('short_trigger_pulse', self.kinds(code))

    def test_inner_variable_guard_cannot_validate_outer_measurement(self):
        source = self.pulse('''{
int duration = 1;
if (duration == 0) return;
float localDistance = duration / 58.0;
}
float distance = duration / 58.0;''')
        self.assertIn('unchecked_no_echo', self.kinds(source))

    def test_inner_unrelated_conversion_does_not_warn_about_outer_measurement(self):
        source = self.pulse('''{
int duration = 1;
float localDistance = duration / 58.0;
}
if (duration == 0) return;
float distance = duration / 58.0;''')
        self.assertNotIn('unchecked_no_echo', self.kinds(source))

    def test_line_continued_comment_is_ignored(self):
        source = '// comment ' + '\\\n' + 'pulseIn(echoPin, HIGH);\n'
        self.assertEqual(self.kinds(source), set())

    def test_unknown_function_does_not_prove_short_pulse(self):
        code = '''void loop() {
digitalWrite(trigPin, HIGH);
waitForSensor(); delayMicroseconds(4);
digitalWrite(trigPin, LOW);
}'''
        self.assertNotIn('short_trigger_pulse', self.kinds(code))

    def test_simple_safe_guard_variants(self):
        for guard in ['if (duration == 0) return;', 'if (!duration) return;',
                      'if (0 == duration) { return; }', 'if ((duration == 0)) return;',
                      'if (duration <= 0) { Serial.println("No echo"); return; }']:
            with self.subTest(guard=guard):
                self.assertNotIn('unchecked_no_echo', self.kinds(self.pulse(
                    guard + '\nfloat distance = duration / 58.0;')))

    def test_positive_guard_and_else_are_safe(self):
        for tail in ['if (duration != 0) { float d = duration / 58.0; }',
                     'if (duration > 0) { float d = duration / 58.0; }',
                     'if (duration == 0) { Serial.println("No echo"); } else { float d = duration / 58.0; }',
                     'if (duration != 0) { Serial.println("Echo"); } else return; float d = duration / 58.0;']:
            with self.subTest(tail=tail):
                self.assertNotIn('unchecked_no_echo', self.kinds(self.pulse(tail)))

    def test_all_nested_branches_return_safely(self):
        source = self.pulse('''if (duration == 0) {
if (emergency) return; else return;
}
float distance = duration / 58.0;''')
        self.assertNotIn('unchecked_no_echo', self.kinds(source))

    def test_nonterminating_guard_is_not_safe(self):
        source = self.pulse('if (duration == 0) Serial.println("No echo");\nfloat d = duration / 58.0;')
        self.assertIn('unchecked_no_echo', self.kinds(source))

    def test_loop_return_or_break_does_not_protect_following_conversion(self):
        for body in ['while (retry) { return; }', 'while (retry) { break; }']:
            with self.subTest(body=body):
                source = self.pulse('if (duration == 0) { ' + body + ' }\nfloat d = duration / 58.0;')
                self.assertIn('unchecked_no_echo', self.kinds(source))

    def test_reassignment_invalidates_guard(self):
        source = self.pulse('if (duration == 0) return;\nduration = readAgain();\nfloat d = duration / 58.0;')
        self.assertIn('unchecked_no_echo', self.kinds(source))

    def test_second_measurement_requires_its_own_guard(self):
        source = self.pulse('if (duration == 0) return;\nduration = pulseIn(echoPin, HIGH, 30000);\nfloat d = duration / 58.0;')
        findings = analyze_hc_sr04(source)
        self.assertEqual([(f.kind, f.line) for f in findings], [('unchecked_no_echo', 4)])

    def test_guard_has_no_arbitrary_fifteen_line_limit(self):
        source = self.pulse('\n' * 20 + 'if (duration == 0) return;\nfloat d = duration / 58.0;')
        self.assertNotIn('unchecked_no_echo', self.kinds(source))

    def test_comments_and_literals_preserve_real_call_line(self):
        code = '''/* pulseIn(echoPin, HIGH)
comment */
void loop() {
Serial.println("http://example.com");
long duration = pulseIn(echoPin, HIGH);
float d = duration / 58.0;
}'''
        self.assertEqual({f.line for f in analyze_hc_sr04(code)}, {5})

    def test_nested_timeout_expression_is_present(self):
        source = 'void loop() { long duration = pulseIn(\nechoPin, HIGH, min(limit, 30000)); if (!duration) return; float d = duration / 58.0; }'
        self.assertEqual(self.kinds(source), set())

    def test_configurable_symbols_and_unrelated_pins(self):
        source = 'void loop() { digitalWrite(TRIG, HIGH); delayMicroseconds(4); digitalWrite(TRIG, LOW); long d = pulseIn(ECHO, HIGH); float cm = d / 58.0; }'
        self.assertEqual(self.kinds(source), set())
        self.assertEqual(self.kinds(source, trig_symbol='TRIG', echo_symbol='ECHO'),
                         {'short_trigger_pulse', 'missing_echo_timeout', 'unchecked_no_echo'})

    def test_multiple_delays_still_sum(self):
        for delay, short in [('4', True), ('5', False)]:
            source = f'void loop() {{ digitalWrite(trigPin, HIGH); delayMicroseconds({delay}); delayMicroseconds({delay}); digitalWrite(trigPin, LOW); }}'
            self.assertEqual('short_trigger_pulse' in self.kinds(source), short)

    def test_bundled_examples_keep_expected_results(self):
        root = Path(__file__).resolve().parents[1] / 'data/sample_projects/obstacle_robot'
        self.assertEqual(self.kinds((root / 'broken_robot.ino').read_text()),
                         {'short_trigger_pulse', 'missing_echo_timeout', 'unchecked_no_echo'})
        self.assertEqual(self.kinds((root / 'fixed_robot.ino').read_text()), set())


if __name__ == '__main__':
    unittest.main()
