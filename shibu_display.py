# ==============================
# Shibu OLED Display Controller (emoji-only mode)
# ==============================
# Shows only emotion bitmaps from 27_human_emotions_oled_data.csv
# Compatible with SSD1306 128x64 OLED on Raspberry Pi 5
# ==============================

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import Image
import pandas as pd
import time
from threading import Lock


class ShibuDisplay:
    def __init__(self):
        self.device = None
        self.emotion_bitmaps = {}
        self.display_lock = Lock()

    def initialize(self):
        """Initializes the OLED and loads emotion bitmaps."""
        try:
            print("[Display] Initializing OLED...")
            serial = i2c(port=1, address=0x3C)
            self.device = ssd1306(serial)

            if not self._load_emotions_from_csv():
                print("[Error] Display: Could not load emotions, disabling OLED.")
                self.device = None
                return

            # pick first available emotion dynamically
            default_emotion = next(iter(self.emotion_bitmaps.keys()))
            self.show_emotion(default_emotion)
            print(f"[Display] OLED Display Initialized and showing '{default_emotion}' face.")

        except Exception as e:
            print(f"[Error] Display: Could not initialize OLED: {e}")
            print("Check if I2C is enabled and OLED connected correctly.")
            self.device = None

    def _load_emotions_from_csv(self, csv_path="27_human_emotions_oled_data.csv"):
        """Loads emotion pixel data from CSV."""
        print(f"[Display] Loading emotions from {csv_path}...")
        try:
            df = pd.read_csv(csv_path)
        except FileNotFoundError:
            print(f"[Error] Display: Cannot find {csv_path}")
            return False
        except Exception as e:
            print(f"[Error] Display: Failed to read CSV: {e}")
            return False

        loaded = 0
        for index, row in df.iterrows():
            try:
                name = str(row["Emotion_Name"]).lower().strip()
                width, height = int(row["Display_Width"]), int(row["Display_Height"])
                pixel_string = str(row["Pixel_Data_String"]).strip()

                if width != 128 or height != 64:
                    print(f"[Warn] Skipping '{name}': Invalid size {width}x{height}")
                    continue

                # Convert '1' to ON pixel (white)
                pixels = [0 if bit == "0" else 255 for bit in pixel_string]

                if len(pixels) != width * height:
                    print(f"[Warn] Skipping '{name}': Pixel length mismatch.")
                    continue

                image = Image.new("1", (width, height))
                image.putdata(pixels)
                self.emotion_bitmaps[name] = image
                loaded += 1

            except Exception as e:
                print(f"[Error] Failed to load emotion '{row.get('Emotion_Name', '?')}': {e}")

        if not self.emotion_bitmaps:
            print("[Error] No valid emotions loaded.")
            return False

        print(f"[Display] Loaded {loaded} emotions successfully.")
        return True

    def show_emotion(self, emotion_name):
        """Displays a given emotion (emoji face) from the loaded CSV."""
        if not self.device:
            return

        emotion_name = str(emotion_name).lower().strip()
        image = self.emotion_bitmaps.get(emotion_name)

        if not image:
            print(f"[Warn] Emotion '{emotion_name}' not found, showing first available.")
            image = next(iter(self.emotion_bitmaps.values()))

        try:
            with self.display_lock:
                with canvas(self.device) as draw:
                    draw.bitmap((0, 0), image.convert("1"), fill=255)
            print(f"[Display] Emotion shown: {emotion_name}")
        except Exception as e:
            print(f"[Error] Display: {e}")

    def clear(self):
        """Clears the OLED."""
        if not self.device:
            return
        with self.display_lock:
            with canvas(self.device) as draw:
                draw.rectangle((0, 0, self.device.width, self.device.height), outline=0, fill=0)
        print("[Display] OLED cleared.")
