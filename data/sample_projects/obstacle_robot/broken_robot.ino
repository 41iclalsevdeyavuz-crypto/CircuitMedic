const int trigPin = 9;
const int echoPin = 10;
void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  Serial.begin(9600);
}
void loop() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(4); // Bug: needs at least 10 us
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH); // Bug: no timeout
  float distanceCm = duration / 58.0;     // Bug: zero unchecked
  if (distanceCm < 30) Serial.println("STOP");
  else Serial.println("FORWARD");
  delay(20);
}
