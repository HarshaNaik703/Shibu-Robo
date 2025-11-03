import time
import os
import glob
import speech_recognition as sr
from gtts import gTTS
import requests  # For Gemini API (fallback)
# from llama_cpp import Llama  # Uncomment if using TinyDolphin / Gemma locally


class ShibuCore:
    def __init__(self):
        self.recognizer = None
        self.mic = None
        self.commands_dir = "./commands"
        self.gemini_api_key = "AIzaSyD77bqIojjW_MC3tFBSc7W_OiJ578j7QGA"

    # ---------------- Initialization ----------------
    def initialize(self):
        print("[Core] Booting Shibu...")

        # Initialize Speech Recognizer
        try:
            self.recognizer = sr.Recognizer()
            self.mic = sr.Microphone(device_index=0)
            print("[Audio] Microphone initialized successfully.")
        except Exception as e:
            print(f"[Error] Mic init failed: {e}")
            self.recognizer = None
            self.mic = None

        # Greet
        self.speak("Hello, I am Shibu. Ready to assist you!")

    # ---------------- Speech Output ----------------
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

    # ---------------- Speech Input ----------------
    def listen(self):
        """Listen for user speech and return recognized text."""
        if not self.recognizer or not self.mic:
            print("[Error] Speech recognizer not initialized.")
            return None

        with self.mic as source:
            print("[Audio] Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
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

    # ---------------- Command Handler ----------------
    def handle_command(self, command):
        """Main decision pipeline."""
        if not command:
            return

        print(f"[Command] Received: {command}")
        file_path = self.find_local_command(command)

        if file_path:
            self.speak(f"Executing task for {command}")
            self.execute_file(file_path)
        else:
            self.speak("I couldn’t find an exact match. Checking patterns...")
            predicted_file = self.query_local_llm(command)

            if predicted_file:
                self.speak(f"I found something similar. Executing {predicted_file}")
                self.execute_file(predicted_file)
            else:
                self.speak("Let me check with Gemini before proceeding.")
                feasible = self.query_gemini(command)

                if feasible:
                    self.speak("Gemini confirmed feasibility. Proceeding safely.")
                    # You can choose to execute default or suggested file here
                else:
                    self.speak("Gemini suggests not executing this command.")

    # ---------------- File Search ----------------
    def find_local_command(self, command):
        """Search for command file by keyword."""
        pattern = command.replace(" ", "_")
        files = glob.glob(os.path.join(self.commands_dir, f"*{pattern}*"))
        if files:
            print(f"[File] Found: {files[0]}")
            return files[0]
        else:
            print("[File] No exact match found.")
            return None

    # ---------------- Execute Local File ----------------
    def execute_file(self, path):
        """Execute a local file (Python script or other)."""
        try:
            if path.endswith(".py"):
                os.system(f"python3 {path}")
            else:
                os.system(path)
        except Exception as e:
            self.speak(f"Error executing {path}: {e}")

    # ---------------- Local LLM (TinyDolphin / Gemma3) ----------------
    def query_local_llm(self, command):
        """
        Use local lightweight LLM to infer best match among directory files.
        You can replace this stub with llama-cpp or any other local model.
        """
        try:
            available_files = [os.path.basename(f) for f in glob.glob(f"{self.commands_dir}/*")]
            # --- Placeholder simple pattern logic ---
            for f in available_files:
                if any(word in f for word in command.split()):
                    return os.path.join(self.commands_dir, f)
            return None

            # Example for real local LLM:
            # llm = Llama(model_path="./models/tiny_dolphin.gguf")
            # prompt = f"User said: '{command}'. Which of these files best matches?\n{available_files}"
            # output = llm(prompt)
            # return parse_llm_result(output)
        except Exception as e:
            print(f"[LLM Error] {e}")
            return None

    # ---------------- Gemini Fallback ----------------
    def query_gemini(self, command):
        """Query Gemini API for feasibility check."""
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": self.gemini_api_key}
            data = {
                "contents": [
                    {"parts": [{"text": f"Check if this command is safe and executable: '{command}'"}]}
                ]
            }
            response = requests.post(url, headers=headers, params=params, json=data)
            result = response.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            print("[Gemini Response]", text)
            return "safe" in text.lower() or "yes" in text.lower()
        except Exception as e:
            print(f"[Gemini Error] {e}")
            return False

    # ---------------- Main Loop ----------------
    def run(self):
        """Continuous listening and handling."""
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
