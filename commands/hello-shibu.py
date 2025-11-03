import serial
import time

# ======================================================
# 🧠 UART CONFIGURATION (GPIO UART)
# ======================================================
# TX -> GPIO14 (Pin 8)
# RX -> GPIO15 (Pin 10)
# GND -> GND (common ground)
# Enable UART using: sudo raspi-config → Interface Options → Serial → 
#   - Disable login shell over serial
#   - Enable serial hardware
# Then reboot the Pi.

SERIAL_PORT = "/dev/serial0"   # symbolic link to Pi's primary UART
BAUD_RATE = 115200

# ======================================================
# 🔌 SERIAL CONNECTION
# ======================================================
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # wait for serial to stabilize

print("🤖 Shibu connected to Arduino Mega over GPIO UART")
print("Use Ctrl+C to stop\n")

DEFAULT_DURATION = 5.0  # seconds

try:
    while True:
        # Ask duration from user (default = 5 seconds)
        duration = input(f"Enter move time in seconds (default {DEFAULT_DURATION}): ").strip()

        if duration == "":
            duration = DEFAULT_DURATION
        else:
            try:
                duration = float(duration)
            except ValueError:
                print("⚠️ Invalid input, using default 5 seconds.\n")
                duration = DEFAULT_DURATION

        # Construct command for Arduino
        cmd = f"<0,{duration}s>\n"
        ser.write(cmd.encode())
        print(f"📤 Sent: {cmd.strip()}")

        # Wait for Arduino reply
        start = time.time()
        reply = ""
        while time.time() - start < duration + 5:  # wait slightly longer
            if ser.in_waiting:
                reply = ser.readline().decode(errors="ignore").strip()
                if reply:
                    print(f"📥 Arduino: {reply}")
                    break
            time.sleep(0.1)

        if not reply:
            print("⏳ No reply (still executing or check wiring)")

        print("-----------\n")
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Stopping...")

finally:
    ser.close()
    print("🔌 Serial connection closed.")
