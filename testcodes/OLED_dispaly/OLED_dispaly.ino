#include <Wire.h>
#include <U8g2lib.h>

// ✅ For 1.3" I2C OLED with SH1106 driver
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE);

void setup() {
  u8g2.begin();  // Initialize display
}

void loop() {
  u8g2.clearBuffer();                // Clear display memory
  u8g2.setFont(u8g2_font_ncenB14_tr); // Choose a readable bold font
  u8g2.drawStr(10, 40, "Hello World"); // Draw text at X=10, Y=40
  u8g2.sendBuffer();                 // Send to display
  delay(1000);
}
