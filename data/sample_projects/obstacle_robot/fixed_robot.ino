const int trigPin = 9;
const int echoPin = 10;

void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  Serial.begin(9600);
}

void loop() {
  // Starting a clean trigger pulse.
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  // HC-SR04 requires TRIG to stay HIGH for at least 10 us.
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // Waiting for the echo for a bounded amount of time.
  long duration = pulseIn(echoPin, HIGH, 30000);

  // pulseIn returns 0 when no echo is received before the timeout.
  if (duration == 0) {
    Serial.println("NO ECHO - STOP");
    delay(70);
    return;
  }

  float distanceCm = duration / 58.0;

  if (distanceCm < 30) {
    Serial.println("STOP");
  } else {
    Serial.println("FORWARD");
  }

  // Keeping the measurements more than 60 ms apart.
  delay(70);
}