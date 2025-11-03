import time
import speech_recognition as sr
from gtts import gTTS
import os

class ShibuCore:
    def __init__(self):
        self.recognizer = None
        self.mic = None

    def initialize(self):
        print("[Core] Booting Shibu...")

        # Initialize Speech Recognizer
        try:
            self.recognizer = sr.Recognizer()
            self.mic = sr.Microphone(device_index=0)  # Use USB mic index from your test
            print("[Audio] Microphone initialized successfully.")
        except Exception as e:
            print(f"[Error] Mic init failed: {e}")
            self.recognizer = None
            self.mic = None

        # Greet
        self.speak("Hello, I am Shibu. Ready to assist you!")

    def speak(self, text):
        """Speak text using Google TTS."""
        print(f"[Shibu says] {text}")
        try:
            tts = gTTS(text=text, lang='en')
            filename = "shibu_voice.mp3"
            tts.save(filename)
            os.system(f"mpg123 -q {filename}")
            os.remove(filename)
        except Exception as e:
            print(f"[Error] TTS failed: {e}")

    def listen(self):
        """Listen for user speech and return recognized text."""
        if not self.recognizer or not self.mic:
            print("[Error] Speech recognizer not initialized.")
            return None

        with self.mic as source:
            print("[Audio] Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = self.recognizer.listen(source, phrase_time_limit=5)

        try:
            text = self.recognizer.recognize_google(audio)
            print(f"[User said] {text}")
            return text.lower()
        except sr.UnknownValueError:
            print("[Audio] Didn't catch that.")
            return None
        except sr.RequestError as e:
            print(f"[Error] Google Speech service failed: {e}")
            return None

    def handle_command(self, command):
        """Handle recognized voice commands (speech only)."""
        if not command:
            return

        if "hello" in command:
            self.speak("Hello there! How are you?")
        elif "sad" in command:
            self.speak("Don't be sad, I am here with you.")
        elif "angry" in command:
            self.speak("Take a deep breath. Calm down.")
        elif "bye" in command or "shutdown" in command:
            self.speak("Goodbye! Shutting down.")
            exit(0)
        else:
            self.speak("I am not sure what that means.")

    def run(self):
        """Main loop."""
        try:
            while True:
                command = self.listen()
                self.handle_command(command)
        except KeyboardInterrupt:
            print("\n[Core] Shutting down.")
            self.speak("Goodbye!")
            time.sleep(1)
            print("[Core] Shutdown complete.")


if __name__ == "__main__":
    shibu = ShibuCore()
    shibu.initialize()
    shibu.run()
