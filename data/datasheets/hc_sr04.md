# HC-SR04 Technical Notes

These concise notes preserve the operating requirements needed by the MVP. They can later be supplemented with a manufacturer PDF.

## Trigger timing
To begin a measurement, drive the TRIG input HIGH for a minimum of 10 microseconds. The module then emits an ultrasonic burst and raises ECHO for a duration proportional to the round-trip time.

## Echo timing and distance
The ECHO pulse width represents the sound round-trip time. Distance in centimetres is commonly calculated as pulse duration divided by 58. Measurements should be separated by a cycle longer than 60 milliseconds to reduce interference from the previous burst.

## Range and no-echo behavior
The typical measuring range is approximately 2 cm to 400 cm. If no echo arrives, software must stop waiting after a bounded interval and treat the reading as unavailable rather than as a valid zero-centimetre distance.

## Electrical interface
The module is normally operated from 5 V. TRIG is an input and ECHO is a TTL-level output. Verify the receiving microcontroller's input-voltage tolerance before direct connection.
