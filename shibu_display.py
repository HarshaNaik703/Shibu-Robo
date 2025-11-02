from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image
import pandas as pd
from threading import Lock

class ShibuDisplay:
    def __init__(self):
        self.device = None
        self.emotion_bitmaps = {}
        self.display_lock = Lock()
        
    def initialize(self):
        """Initializes the connection to the 128x64 OLED display."""
        try:
            serial = i2c(port=1, address=0x3C)
            self.device = ssd1306(serial)
            
            if not self._load_emotions_from_csv():
                self.device = None
                return
                
            self.show_emotion("neutral") # Start with a neutral face
            print("[Display] OLED Display Initialized.")
        except Exception as e:
            print(f"[Error] Display: Could not initialize OLED display: {e}")
            print("Is the display connected correctly? Is 'i2c' enabled in raspi-config?")
            self.device = None

    def _load_emotions_from_csv(self, csv_path="27_human_emotions_oled_data.csv"):
        """Loads the emotion data from CSV."""
        print(f"[Display] Loading emotions from {csv_path}...")
        try:
            df = pd.read_csv(csv_path)
        except FileNotFoundError:
            print(f"[Error] Display: Cannot find {csv_path}")
            return False

        for index, row in df.iterrows():
            try:
                name = row['Emotion_Name'].lower().strip()
                width, height = int(row['Display_Width']), int(row['Display_Height'])
                pixel_string = str(row['Pixel_Data_String'])
                if width != 128 or height != 64:
                    print(f"[Warn] Skipping '{name}': invalid dimensions.")
                    continue
                image = Image.new('1', (width, height))
                pixels = [255 if bit == '1' else 0 for bit in pixel_string]
                if len(pixels) != (width * height):
                    print(f"[Warn] Skipping '{name}': length mismatch.")
                    continue
                image.putdata(pixels)
                self.emotion_bitmaps[name] = image
            except Exception as e:
                print(f"[Error] Failed to parse row {index} ('{name}'): {e}")
                
        if not self.emotion_bitmaps:
            print("[Error] No emotions were loaded.")
            return False
        
        print(f"[Display] Loaded {len(self.emotion_bitmaps)} emotions.")
        return True

    def show_emotion(self, emotion_name):
        """Displays an emotion image."""
        if not self.device:
            return
        emotion_name = emotion_name.lower().strip()
        image_to_draw = self.emotion_bitmaps.get(emotion_name, self.emotion_bitmaps.get("neutral"))
        if image_to_draw:
            try:
                with self.display_lock:
                    self.device.display(image_to_draw)
            except Exception as e:
                print(f"[Error] Display: {e}")

