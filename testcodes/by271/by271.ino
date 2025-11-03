#include <QMC5883LCompass.h>  // QMC5883L (GY-271) compatible library
#include <Wire.h>

QMC5883LCompass compass;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  compass.init();                 // start QMC5883L (default addr 0x0D)
  // Optional: if your library supports it, set smoothing or calibration
  // compass.setSmoothing(10, true);
  // After you run a calibration routine, you can set hard-iron offsets:
  // compass.setCalibration(xmin, xmax, ymin, ymax, zmin, zmax);
}

void loop() {
  compass.read();                 // update internal measurements
  int az = compass.getAzimuth();  // 0..359 degrees
  if (az < 0) az += 360;          // ensure non-negative
  Serial.println(az);
  delay(100);                     // ~10 Hz
}
