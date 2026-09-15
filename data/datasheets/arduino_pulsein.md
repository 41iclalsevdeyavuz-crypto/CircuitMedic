# Arduino pulseIn Reference

## Default timeout behavior

Arduino's pulseIn() function measures the duration of a pulse on a pin.

The timeout parameter is optional.

If no timeout is explicitly supplied, pulseIn() uses its default timeout behavior rather than waiting forever.

For control loops that require fast response, an explicit timeout can be preferable so the program does not wait longer than the application's measurement cycle allows.

## Timeout return value

If no pulse starts before the timeout expires, pulseIn() returns 0.

A return value of 0 therefore represents a timeout or unavailable pulse measurement, not a valid measured pulse duration.

Application code should handle this case before converting the returned duration into a physical measurement such as distance.

The appropriate fallback behavior depends on the application. CircuitMedic does not assume whether the robot should stop, reverse, retry, or take another action.

Source:
Arduino Language Reference — pulseIn()
https://docs.arduino.cc/language-reference/en/functions/advanced-io/pulseIn/