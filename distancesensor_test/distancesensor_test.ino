#include <Wire.h>
#include <VL53L0X.h>

VL53L0X sensorFront;
VL53L0X sensorBack;
VL53L0X sensorLeft;
VL53L0X sensorRight;

// XSHUT control pins
#define XSHUT_FRONT 22
#define XSHUT_BACK  23
#define XSHUT_LEFT  24
#define XSHUT_RIGHT 25

void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(XSHUT_FRONT, OUTPUT);
  pinMode(XSHUT_BACK,  OUTPUT);
  pinMode(XSHUT_LEFT,  OUTPUT);
  pinMode(XSHUT_RIGHT, OUTPUT);

  // Shutdown all sensors initially
  digitalWrite(XSHUT_FRONT, LOW);
  digitalWrite(XSHUT_BACK,  LOW);
  digitalWrite(XSHUT_LEFT,  LOW);
  digitalWrite(XSHUT_RIGHT, LOW);
  delay(10);

  // Sequentially enable and assign new addresses
  digitalWrite(XSHUT_FRONT, HIGH);
  delay(10);
  sensorFront.init();
  sensorFront.setAddress(0x30);

  digitalWrite(XSHUT_BACK, HIGH);
  delay(10);
  sensorBack.init();
  sensorBack.setAddress(0x31);

  digitalWrite(XSHUT_LEFT, HIGH);
  delay(10);
  sensorLeft.init();
  sensorLeft.setAddress(0x32);

  digitalWrite(XSHUT_RIGHT, HIGH);
  delay(10);
  sensorRight.init();
  sensorRight.setAddress(0x33);

  // Start continuous ranging
  sensorFront.startContinuous();
  sensorBack.startContinuous();
  sensorLeft.startContinuous();
  sensorRight.startContinuous();

  Serial.println("✅ VL53L0X sensors initialized (Front/Back/Left/Right)");
}

void loop() {
  int dF = sensorFront.readRangeContinuousMillimeters();
  int dB = sensorBack.readRangeContinuousMillimeters();
  int dL = sensorLeft.readRangeContinuousMillimeters();
  int dR = sensorRight.readRangeContinuousMillimeters();

  Serial.print("Front: "); Serial.print(dF); Serial.print(" mm, ");
  Serial.print("Back: ");  Serial.print(dB); Serial.print(" mm, ");
  Serial.print("Left: ");  Serial.print(dL); Serial.print(" mm, ");
  Serial.print("Right: "); Serial.print(dR); Serial.println(" mm");

  delay(200);
}

