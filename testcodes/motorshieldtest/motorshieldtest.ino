// mega_l293d_afmotor_test.ino
// Tests Adafruit L293D Motor Shield v1 (AFMotor library) on M1..M4.
// Mega-compatible. Provide external motor supply as required.

#include <AFMotor.h>  // Adafruit Motor Shield v1 library

AF_DCMotor M1(1);     // Channel M1
AF_DCMotor M2(2);     // Channel M2
AF_DCMotor M3(3);     // Channel M3
AF_DCMotor M4(4);     // Channel M4

void stopAll() {
  M1.run(RELEASE); M1.setSpeed(0);
  M2.run(RELEASE); M2.setSpeed(0);
  M3.run(RELEASE); M3.setSpeed(0);
  M4.run(RELEASE); M4.setSpeed(0);
}

void rampMotor(AF_DCMotor& m, uint8_t chan, uint8_t dir) {
  m.run(dir);
  for (int s = 0; s <= 255; s += 25) {
    m.setSpeed(s);
    Serial.print("M"); Serial.print(chan);
    Serial.print(dir == FORWARD ? " F " : " B ");
    Serial.println(s);
    delay(150);
  }
  // Hold max for a second
  delay(1000);
  // Coast to stop
  m.run(RELEASE);
  m.setSpeed(0);
  delay(500);
}

void setup() {
  Serial.begin(115200);
  Serial.println("AFMotor L293D 4-DC test");
  // Ensure all released at start
  stopAll();
}

void loop() {
  // Test each motor forward then backward
  Serial.println("M1 forward");
  rampMotor(M1, 1, FORWARD);
  Serial.println("M1 backward");
  rampMotor(M1, 1, BACKWARD);

  Serial.println("M2 forward");
  rampMotor(M2, 2, FORWARD);
  Serial.println("M2 backward");
  rampMotor(M2, 2, BACKWARD);

  Serial.println("M3 forward");
  rampMotor(M3, 3, FORWARD);
  Serial.println("M3 backward");
  rampMotor(M3, 3, BACKWARD);

  Serial.println("M4 forward");
  rampMotor(M4, 4, FORWARD);
  Serial.println("M4 backward");
  rampMotor(M4, 4, BACKWARD);

  // All motors together forward at medium speed
  Serial.println("All motors forward @180");
  M1.run(FORWARD); M2.run(FORWARD); M3.run(FORWARD); M4.run(FORWARD);
  M1.setSpeed(180); M2.setSpeed(180); M3.setSpeed(180); M4.setSpeed(180);
  delay(2000);

  // All motors backward at medium speed
  Serial.println("All motors backward @180");
  M1.run(BACKWARD); M2.run(BACKWARD); M3.run(BACKWARD); M4.run(BACKWARD);
  delay(2000);

  // Stop
  stopAll();
  Serial.println("Done cycle; pausing...");
  delay(3000);
}
