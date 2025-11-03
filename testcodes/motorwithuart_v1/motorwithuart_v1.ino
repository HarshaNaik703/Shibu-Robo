// Place type and prototype BEFORE any includes to avoid Arduino auto-prototype issues
struct Cmd { int deg; uint32_t ms; bool valid; };
bool tryReadCmd(struct Cmd &cmd);

#include <AFMotor.h>
#include <Wire.h>
#include <QMC5883LCompass.h>

QMC5883LCompass compass;

AF_DCMotor M_FR(1);  // Front Right - M1
AF_DCMotor M_FL(2);  // Front Left  - M2
AF_DCMotor M_BL(3);  // Back  Left  - M3
AF_DCMotor M_BR(4);  // Back  Right - M4

static inline int norm360(int x) { x %= 360; if (x < 0) x += 360; return x; }
static inline int shortestErr(int target, int current) { int e = target - current; if (e > 180) e -= 360; if (e < -180) e += 360; return e; }

void stopall() {
  M_FR.run(RELEASE); M_FR.setSpeed(0);
  M_FL.run(RELEASE); M_FL.setSpeed(0);
  M_BL.run(RELEASE); M_BL.setSpeed(0);
  M_BR.run(RELEASE); M_BR.setSpeed(0);
}

void setup() {
  Serial.begin(115200);      // USB debug
  Serial1.begin(115200);     // RPi5 link on Mega Serial1 (RX1=19, TX1=18)
  Serial.println("AFMotor L293D + QMC5883L + Serial1 command interface");
  Wire.begin();
  compass.init();
  stopall();
  delay(200);
}

void rotate(int16_t deg) {
  // Capture starting and target headings
  compass.read();
  int start  = norm360(compass.getAzimuth());
  int target = norm360(start + deg);

  // Tunables
  const uint8_t minSpeed   = 70;
  const uint8_t maxSpeed   = 150;
  const int     deadband   = 3;
  const uint8_t settleNeed = 6;
  const uint16_t dt_ms     = 10;
  const uint32_t timeoutMs = 8000;
  const float Kp = 1.2f;
  const float Kd = 0.8f;

  unsigned long t0 = millis();
  int prev = start;
  uint8_t settled = 0;

  while (true) {
    if (millis() - t0 > timeoutMs) break;

    compass.read();
    int cur = norm360(compass.getAzimuth());
    int err = shortestErr(target, cur);
    int mag = abs(err);

    // Angular velocity estimate (deg/s)
    int dtheta = shortestErr(cur, prev);
    float omega = (float)dtheta * (1000.0f / dt_ms);
    prev = cur;

    if (mag <= deadband) {
      if (++settled >= settleNeed) {
        // Active plug-brake proportional to recent omega
        uint8_t brake = (uint8_t)constrain((int)(minSpeed + 0.3f * fabs(omega)), 60, 140);
        unsigned long bp = constrain((unsigned long)(5 + 0.6f * fabs(omega)), 20UL, 120UL);

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
        stopall();
        break;
      }
    } else {
      settled = 0;
    }

    // PD control on angle error and rate
    int u = (int)(Kp * mag - Kd * fabs(omega)/50.0f);
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

// Forward move with yaw-hold to maintain heading
void move(uint32_t duration_ms) {
  // Timing profile (trapezoid)
  const uint16_t dt_ms       = 10;
  const uint16_t accel_ms    = 500;
  const uint16_t decel_ms    = 600;
  const uint8_t  v_min       = 70;
  const uint8_t  v_cruise    = 150;

  // Yaw hold PD
  const float Kp_yaw         = 2.2f;
  const float Kd_yaw         = 0.9f;

  // End-of-run braking
  const uint8_t  brake_min_spd = 60;
  const uint8_t  brake_max_spd = 140;
  const uint16_t brake_min_ms  = 30;
  const uint16_t brake_max_ms  = 120;

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

  int prev = target;

  while (t < duration_ms) {
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
    int err     = shortestErr(target, current);
    int dtheta  = shortestErr(current, prev);
    float omega = (float)dtheta * (1000.0f / dt_ms);
    prev = current;

    // PD yaw correction (left/right differential)
    float corr = Kp_yaw * (float)err + Kd_yaw * omega;
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
  compass.read();
  int now  = norm360(compass.getAzimuth());
  int dth  = shortestErr(now, prev);
  float om = (float)dth * (1000.0f / dt_ms);
  uint8_t  bspd = (uint8_t)constrain((int)(v_min + 0.35f * fabs(om)), brake_min_spd, brake_max_spd);
  uint16_t bms  = (uint16_t)constrain((int)(40 + 0.7f * fabs(om)), brake_min_ms, brake_max_ms);

  // Brief reverse to cancel inertia, then stop
  M_FL.setSpeed(bspd); M_BL.setSpeed(bspd); M_FR.setSpeed(bspd); M_BR.setSpeed(bspd);
  M_FL.run(FORWARD);   M_BL.run(FORWARD);   M_FR.run(FORWARD);   M_BR.run(FORWARD);
  delay(bms);

  stopall();
  delay(150);
}

// -------- Serial1 command parser --------
// Accepts: "<deg><time_ms>", "<deg,time_ms>", or "deg time_ms\n"
// Optional 's' suffix for seconds, e.g., "<90,5s>"
bool tryReadCmd(struct Cmd &cmd) {
  static char line[64];
  static size_t idx = 0;

  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[idx] = '\0';
      idx = 0;

      String s(line);
      s.trim();
      // Normalize various bracketed forms to "deg,time"
      s.replace("><", ",");
      s.replace("<", "");
      s.replace(">", "");
      s.replace(";", ",");
      s.replace("\t", " ");
      s.trim();
      // Collapse spaces to comma
      while (s.indexOf("  ") >= 0) s.replace("  ", " ");
      s.replace(" ", ",");

      int sep = s.indexOf(',');
      if (sep < 0) { cmd.valid = false; return false; }
      String a = s.substring(0, sep); a.trim();
      String b = s.substring(sep + 1); b.trim();
      if (a.length() == 0 || b.length() == 0) { cmd.valid = false; return false; }

      long deg = a.toInt();
      unsigned long ms = 0UL;
      if (b.endsWith("s") || b.endsWith("S")) {
        b.remove(b.length()-1);
        ms = (unsigned long)(b.toFloat() * 1000.0f);
      } else {
        ms = strtoul(b.c_str(), nullptr, 10);
      }

      cmd.deg = (int)deg;
      cmd.ms  = (uint32_t)ms;
      cmd.valid = true;
      return true;
    } else {
      if (idx < sizeof(line) - 1) line[idx++] = c;
      else idx = 0; // overflow: reset
    }
  }
  return false;
}

void loop() {
  // Process commands from Raspberry Pi 5 on Serial1
  Cmd cmd{0,0,false};
  if (tryReadCmd(cmd) && cmd.valid) {
    Serial.print("CMD deg="); Serial.print(cmd.deg);
    Serial.print(" ms="); Serial.println(cmd.ms);

    rotate((int16_t)cmd.deg);
    move(cmd.ms);

    Serial1.println("OK");
  }

  // Idle delay to reduce I2C noise while waiting
  delay(5);
}
