# Arduino pulseIn Reference

## Default timeout behavior

Arduino's pulseIn() function measures the duration of a pulse on a pin.

The timeout parameter is optional.

If no timeout is explicitly supplied, pulseIn() uses its default timeout behavior rather than waiting forever.

For control loops that require fast response, an explicit timeout can be preferable so the program does not wait longer than the application's measurement cycle allows.

Source:
Arduino Language Reference — pulseIn()
https://docs.arduino.cc/language-reference/en/functions/advanced-io/pulseIn/