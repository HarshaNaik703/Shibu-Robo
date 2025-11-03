#include <AFMotor.h>

// Four DC motors on M1..M4
AF_DCMotor M_FR(1);
AF_DCMotor M_FL(2);
AF_DCMotor M_BL(3);
AF_DCMotor M_BR(4);

void setup() {
  uint8_t speed = 180; // 0..255

  M_FR.setSpeed(speed);
  M_FL.setSpeed(speed);
  M_BL.setSpeed(speed);
  M_BR.setSpeed(speed);

  M_FR.run(FORWARD);
  M_FL.run(FORWARD);
  M_BL.run(FORWARD);
  M_BR.run(FORWARD);
}

void loop() {
  // Motors keep runningg forward
}
