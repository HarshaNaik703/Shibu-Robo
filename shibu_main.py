#!/usr/bin/env python3
"""
shibu_main.py — Updated for working microphone input
"""

import os
import time
import glob
import subprocess
import json
import warnings
import sys
import speech_recognition as sr
from gtts import gTTS
import requests

# Environment fixes for ALSA / PulseAudio
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["SDL_AUDIODRIVER"] = "pulseaudio"
os.environ["AUDIODEV"] = "null"
os.environ["ALSA_CARD"] = "0"
os.environ["ALSA_PCM_CARD"] = "0"
os.environ["ALSA_PCM_DEVICE"] = "0"
sys.stderr = open(os.devnull, 'w')
warnings.filterwarnings("ignore")

# optional LLM backend
try:
    from llama_cpp import Llama
except Exception:
    Llama = None

# dotenv for GEMINI_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# optional offline TTS
try:
    import pyttsx3
except Exception:
    pyttsx3 = None


class ShibuCore:
    def __init__(
        self,
        commands_dir: str = "./commands",
        model_path: str = "./models/tinydolphin-1.1b.Q4_K_M.gguf",
        use_local_llm: bool = True,
    ):
        self.recognizer = None
        self.mic = None
        self.commands_dir = commands_dir
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.model_path = model_path
        self.use_local_llm = use_local_llm and (Llama is not None)
        self.llm = None

        if self.use_local_llm:
            if os.path.exists(self.model_path):
                try:
                    print(f"[LLM] Loading local model from: {self.model_path}")
                    self.llm = Llama(model_path=self.model_path)
                    print("[LLM] Model loaded successfully.")
                except Exception as e:
                    print(f"[LLM] Failed to initialize local LLM: {e}")
                    self.llm = None
                    self.use_local_llm = False
            else:
                print(f"[LLM] Model file not found at {self.model_path}. Local LLM disabled.")
                self.llm = None
                self.use_local_llm = False

    # ---------------- Initialization ----------------
    def initialize(self, mic_index: int = 1):
        """Initialize microphone and recognizer (mic_index=1 usually works best on Ubuntu)."""
        print("[Core] Booting Shibu...")

        try:
            self.recognizer = sr.Recognizer()
            self.mic = sr.Microphone(device_index=mic_index)
            print(f"[Audio] Microphone initialized successfully (device_index={mic_index}).")
        except Exception as e:
            print(f"[Error] Mic init failed: {e}")
            self.recognizer = None
            self.mic = None

        self.speak("Hello, I am Shibu. Ready to assist you!")

    # ---------------- Speech Output ----------------
    def speak(self, text: str):
        print(f"[Shibu says] {text}")
        try:
            tts = gTTS(text=text, lang="en")
            filename = "shibu_voice.mp3"
            tts.save(filename)
            try:
                subprocess.run(["mpg123", "-q", filename], check=True)
            except FileNotFoundError:
                if os.name == "nt":
                    os.startfile(filename)
                else:
                    subprocess.run(["aplay", filename], check=False)
            os.remove(filename)
        except Exception as e:
            print(f"[TTS] gTTS failed: {e}")
            if pyttsx3 is not None:
                try:
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    print(f"[TTS] pyttsx3 failed: {e}")
            else:
                print("[TTS] No TTS available.")

    # ---------------- Speech Input ----------------
    def listen(self, phrase_time_limit: int = 5):
        """Listen for user speech and return recognized text (lower-cased)."""
        if not self.recognizer or not self.mic:
            print("[Error] Speech recognizer not initialized.")
            return None

        try:
            with self.mic as source:
                print("[Audio] Listening...")
                print("[Debug] Mic source opened, waiting for speech...")
                audio = None
                try:
                    # Move adjust_for_ambient_noise INSIDE 'with' AFTER mic is opened
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    print("[Debug] Ambient noise adjusted.")
                    audio = self.recognizer.listen(source, phrase_time_limit=phrase_time_limit)
                    print("[Debug] Audio captured successfully.")
                except Exception as e:
                    print(f"[Audio] Listen failed: {e}")
                    return None
        except Exception as e:
            print(f"[Audio] Microphone access error: {e}")
            return None

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
        except Exception as e:
            print(f"[Error] Speech recognition error: {e}")
            return None


    # ---------------- Command Handler ----------------
    def handle_command(self, command: str):
        if not command:
            return

        print(f"[Command] Received: {command}")
        file_path = self.find_local_command(command)
        if file_path:
            self.speak(f"Executing task for {command}")
            self.execute_file(file_path)
            return

        self.speak("I couldn't find an exact match. Checking patterns...")
        predicted_path = self.query_local_llm(command)
        if predicted_path:
            self.speak(f"I found something similar: {os.path.basename(predicted_path)}. Executing.")
            self.execute_file(predicted_path)
            return

        self.speak("Let me check with Gemini before proceeding.")
        feasible = self.query_gemini(command)
        if feasible:
            self.speak("Gemini confirmed feasibility. No local file found though.")
        else:
            self.speak("Gemini suggests not executing this command.")

    # ---------------- File Search ----------------
    def find_local_command(self, command: str):
        if not os.path.exists(self.commands_dir):
            print(f"[File] Commands directory '{self.commands_dir}' does not exist.")
            return None

        pattern = command.strip().lower().replace(" ", "_")
        files = glob.glob(os.path.join(self.commands_dir, f"*{pattern}*"))
        if files:
            print(f"[File] Found exact-ish match: {files[0]}")
            return files[0]

        available_files = glob.glob(os.path.join(self.commands_dir, "*"))
        cmd_words = [w for w in command.lower().split() if len(w) > 2]
        for fpath in available_files:
            fname = os.path.basename(fpath).lower()
            if all(any(w in tok for tok in fname.replace(".", "_").split("_")) for w in cmd_words[:2]):
                print(f"[File] Heuristic match: {fpath}")
                return fpath

        print("[File] No local match found.")
        return None

    # ---------------- Execute Local File ----------------
    def execute_file(self, path: str):
        try:
            if path.endswith(".py"):
                print(f"[Execute] Running python script: {path}")
                subprocess.run(["python3", path], check=False)
            else:
                print(f"[Execute] Running command/file: {path}")
                subprocess.run([path], check=False)
        except Exception as e:
            self.speak(f"Error executing {path}: {e}")

    # ---------------- Local LLM ----------------
    def query_local_llm(self, command: str):
        try:
            available_files = [os.path.basename(f) for f in glob.glob(os.path.join(self.commands_dir, "*"))]
            if not available_files:
                print("[LLM] No files in commands directory to compare.")
                return None

            if not self.llm:
                print("[LLM] Local model not available. Using token similarity fallback.")
                cmd_tokens = [t for t in command.lower().split() if len(t) > 2]
                best_score = 0
                best_file = None
                for fname in available_files:
                    score = sum(1 for t in cmd_tokens if t in fname.lower())
                    if score > best_score:
                        best_score = score
                        best_file = fname
                if best_score > 0:
                    print(f"[LLM-Fallback] Selected {best_file} with score {best_score}")
                    return os.path.join(self.commands_dir, best_file)
                return None

            prompt = (
                f"You are a helper that maps user intent to filenames. "
                f"User said: '{command}'. Available filenames: {available_files}. "
                f"Reply only with the single best matching filename."
            )

            print("[LLM] Querying local model for best match...")
            out = self.llm(prompt, max_tokens=64)
            text = out.get("choices", [{}])[0].get("text", "").strip()
            if not text:
                print("[LLM] Model returned empty response.")
                return None
            for fname in available_files:
                if text.lower() in fname.lower():
                    return os.path.join(self.commands_dir, fname)
            return None

        except Exception as e:
            print(f"[LLM Error] {e}")
            return None

    # ---------------- Gemini Fallback ----------------
    def query_gemini(self, command: str) -> bool:
        if not self.gemini_api_key:
            print("[Gemini] No Gemini API key provided.")
            return False

        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": self.gemini_api_key}
            data = {
                "contents": [{"parts": [{"text": f"Is this command safe: '{command}'? Reply SAFE or UNSAFE."}]}]
            }
            response = requests.post(url, headers=headers, params=params, json=data, timeout=15)
            result = response.json()
            text = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .lower()
            )
            return "safe" in text
        except Exception as e:
            print(f"[Gemini Error] {e}")
            return False

    # ---------------- Main Loop ----------------
    def run(self):
        try:
            while True:
                command = self.listen()
                if command:
                    self.handle_command(command)
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n[Core] Shutting down.")
            self.speak("Goodbye!")
            time.sleep(1)
            print("[Core] Shutdown complete.")


# ---------------- Entrypoint ----------------
if __name__ == "__main__":
    shibu = ShibuCore()
    shibu.initialize(mic_index=1)  # <-- changed from 0 to 1
    shibu.run()
