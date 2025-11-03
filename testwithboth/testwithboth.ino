// mega_l293d_afmotor_simple_test_full.ino
// Adafruit L293D Motor Shield v1 (AFMotor) + QMC5883L (GY-271)
// Mega-compatible. Provide an external motor supply appropriate for your motors.

#include <AFMotor.h>
#include <Wire.h>
#include <QMC5883LCompass.h>

QMC5883LCompass compass;

AF_DCMotor M_FR(1);  // Front Right - M1
AF_DCMotor M_FL(2);  // Front Left  - M2
AF_DCMotor M_BL(3);  // Back  Left  - M3
AF_DCMotor M_BR(4);  // Back  Right - M4

static inline int norm360(int x) {
  x %= 360;
  if (x < 0) x += 360;
  return x;
}

static inline int shortestErr(int target, int current) {
  int e = target - current;
  if (e > 180)  e -= 360;
  if (e < -180) e += 360;
  return e;
}

void stopall() {
  M_FR.run(RELEASE); M_FR.setSpeed(0);
  M_FL.run(RELEASE); M_FL.setSpeed(0);
  M_BL.run(RELEASE); M_BL.setSpeed(0);
  M_BR.run(RELEASE); M_BR.setSpeed(0);
}

void setup() {
  Serial.begin(115200);
  Serial.println("AFMotor L293D + QMC5883L - rotate/move test");
  Wire.begin();
  compass.init();
  // Optional:
  // compass.setSmoothing(10, true);
  // compass.setCalibration(xmin, xmax, ymin, ymax, zmin, zmax);

  stopall();
  delay(200);
}

void rotate(int16_t deg) {
  // Read initial heading
  compass.read();
  auto norm360 = [](int x){ x%=360; if (x<0) x+=360; return x; };
  auto shortestErr = [](int t, int c){ int e=t-c; if(e>180) e-=360; if(e<-180) e+=360; return e; };

  int start  = norm360(compass.getAzimuth());
  int target = norm360(start + deg);

  // Tunables
  const uint8_t minSpeed   = 70;    // lower final approach speed
  const uint8_t maxSpeed   = 150;   // cap to reduce energy/inertia
  const int deadband       = 3;     // degrees
  const uint8_t settleNeed = 6;     // consecutive samples in band
  const uint16_t dt_ms     = 10;    // faster loop for tighter stop
  const uint32_t timeoutMs = 8000;  // safety
  const float Kp = 1.2f;            // proportional on angle error
  const float Kd = 0.8f;            // derivative on angular rate

  unsigned long t0 = millis();
  int prev = start;
  uint8_t settled = 0;

  while (true) {
    if (millis() - t0 > timeoutMs) break;

    compass.read();
    int cur = norm360(compass.getAzimuth());
    int err = shortestErr(target, cur);
    int mag = abs(err);

    // Estimate angular velocity (deg/s) from wrapped delta
    int dtheta = shortestErr(cur, prev);
    float omega = (float)dtheta * (1000.0f / dt_ms); // deg/s
    prev = cur;

    if (mag <= deadband) {
      if (++settled >= settleNeed) {
        // Active brake pulse scaled by recent speed
        uint8_t brake = (uint8_t)constrain((int)(minSpeed + 0.3f * fabs(omega)), 60, 140);
        unsigned long bp = constrain((unsigned long)(5 + 0.6f * fabs(omega)), 20UL, 120UL);

        // Reverse briefly to cancel inertia
        if (omega > 0) {
          // Turning CCW, apply CW brake
          M_FL.setSpeed(brake); M_BL.setSpeed(brake); M_FR.setSpeed(brake); M_BR.setSpeed(brake);
          M_FL.run(FORWARD);  M_BL.run(FORWARD);
          M_FR.run(BACKWARD); M_BR.run(BACKWARD);
        } else if (omega < 0) {
          // Turning CW, apply CCW brake
          M_FL.setSpeed(brake); M_BL.setSpeed(brake); M_FR.setSpeed(brake); M_BR.setSpeed(brake);
          M_FL.run(BACKWARD); M_BL.run(BACKWARD);
          M_FR.run(FORWARD);  M_BR.run(FORWARD);
        }
        delay(bp);
        stopall(); // coast after brake pulse
        break;
      }
    } else {
      settled = 0;
    }

    // PD speed command
    int u = (int)(Kp * mag - Kd * fabs(omega)/50.0f); // scale omega term
    u = constrain(u, minSpeed, maxSpeed);

    if (err > 0) {
      // Need CCW
      M_FL.setSpeed(u); M_BL.setSpeed(u); M_FR.setSpeed(u); M_BR.setSpeed(u);
      M_FL.run(BACKWARD); M_BL.run(BACKWARD);
      M_FR.run(FORWARD);  M_BR.run(FORWARD);
    } else if (err < 0) {
      // Need CW
      M_FL.setSpeed(u); M_BL.setSpeed(u); M_FR.setSpeed(u); M_BR.setSpeed(u);
      M_FL.run(FORWARD);  M_BL.run(FORWARD);
      M_FR.run(BACKWARD); M_BR.run(BACKWARD);
    } else {
      stopall();
      break;
    }

    delay(dt_ms);
  }

  stopall();
  delay(150);
}


// Requires norm360(int) and shortestErr(int,int) helpers from your current sketch.
// Forward mapping here matches your previous code: BACKWARD = forward motion.

void move(uint32_t duration_ms) {
  // Timing profile (trapezoid)
  const uint16_t dt_ms       = 10;    // faster loop for tighter control
  const uint16_t accel_ms    = 500;   // ramp-up time
  const uint16_t decel_ms    = 600;   // ramp-down time
  const uint8_t  v_min       = 70;    // low approach speed (0..255)
  const uint8_t  v_cruise    = 150;   // cruise speed cap (0..255)

  // Yaw hold PD (heading straight)
  const float Kp_yaw         = 2.2f;  // proportional on heading error
  const float Kd_yaw         = 0.9f;  // derivative on yaw rate

  // End-of-run braking (counter-plugging)
  const uint8_t brake_min_spd = 60;
  const uint8_t brake_max_spd = 140;
  const uint16_t brake_min_ms = 30;
  const uint16_t brake_max_ms = 120;

  // Capture target heading
  compass.read();
  int target = norm360(compass.getAzimuth());

  unsigned long t0 = millis();
  unsigned long t  = 0;

  // Start forward (per wiring: BACKWARD means forward)
  M_FR.run(BACKWARD);
  M_FL.run(BACKWARD);
  M_BL.run(BACKWARD);
  M_BR.run(BACKWARD);

  // Track previous heading for omega
  int prev = target;

  while (t < duration_ms) {
    // Time update
    t = millis() - t0;

    // Trapezoidal base speed
    uint8_t base = v_cruise;
    if (t < accel_ms) {
      base = v_min + (uint8_t)((v_cruise - v_min) * (float)t / accel_ms);
    } else if (t > duration_ms - decel_ms) {
      uint32_t tdec = (t > duration_ms) ? decel_ms : (t - (duration_ms - decel_ms));
      float decRatio = 1.0f - (float)tdec / decel_ms;
      if (decRatio < 0) decRatio = 0;
      base = v_min + (uint8_t)((v_cruise - v_min) * decRatio);
    }
    if (base < v_min) base = v_min;
    if (base > v_cruise) base = v_cruise;

    // Read heading and compute yaw error and rate
    compass.read();
    int current = norm360(compass.getAzimuth());
    int err     = shortestErr(target, current);           // deg
    int dtheta  = shortestErr(current, prev);             // deg over dt
    float omega = (float)dtheta * (1000.0f / dt_ms);      // deg/s
    prev = current;

    // PD yaw correction (left/right differential)
    float corr = Kp_yaw * (float)err + Kd_yaw * omega;    // signed
    // Map correction into speed delta; clamp to base to avoid sign flip
    int d = (int)corr;
    if (d > (int)base)  d = base;
    if (d < -(int)base) d = -((int)base);

    int sL = constrain((int)base + d, 0, 255);
    int sR = constrain((int)base - d, 0, 255);

    // Apply speeds (forward = BACKWARD in this wiring)
    M_FL.setSpeed(sL);
    M_BL.setSpeed(sL);
    M_FR.setSpeed(sR);
    M_BR.setSpeed(sR);

    M_FL.run(BACKWARD);
    M_BL.run(BACKWARD);
    M_FR.run(BACKWARD);
    M_BR.run(BACKWARD);

    delay(dt_ms);
  }

  // Active brake pulse proportional to last motion
  // Estimate last omega and base again for braking strength
  compass.read();
  int now    = norm360(compass.getAzimuth());
  int dth    = shortestErr(now, prev);
  float om   = (float)dth * (1000.0f / dt_ms); // deg/s
  uint8_t bspd = (uint8_t)constrain((int)(v_min + 0.35f * fabs(om)), brake_min_spd, brake_max_spd);
  uint16_t bms = (uint16_t)constrain((int)(40 + 0.7f * fabs(om)), brake_min_ms, brake_max_ms);

  // Brief reverse to cancel inertia, then stop
  M_FL.setSpeed(bspd); M_BL.setSpeed(bspd); M_FR.setSpeed(bspd); M_BR.setSpeed(bspd);
  M_FL.run(FORWARD);   M_BL.run(FORWARD);   M_FR.run(FORWARD);   M_BR.run(FORWARD);
  delay(bms);

  // Coast after plug braking
  stopall();
  delay(150);
}


void loop() {
  rotate(90);
  delay(2000);
  rotate(90);
  delay(2000);
  rotate(90);
  // move(5000);
  move(10000);
}
