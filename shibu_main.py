#!/usr/bin/env python3
"""
shibu_main.py

Ready-to-run Shibu core:
- Searches ./commands for a matching script and executes it
- If not found, tries a local LLM (TinyDolphin / Gemma) if available
- If still not found, calls Gemini API (if key provided via .env) for feasibility
- Uses gTTS (online) with mpg123, falls back to pyttsx3 if needed
- Keeps API key out of source via python-dotenv

What to edit:
- Place your executable scripts under ./commands/
- (Optional) Put a local model at ./models/tinydolphin-1.1b.Q4_K_M.gguf or change model_path
- Create a .env file containing GEMINI_API_KEY=your_key_here (or omit for no Gemini)

Dependencies:
pip install speechrecognition gtts requests python-dotenv pyttsx3 llama-cpp-python
(install mpg123 on Linux via apt if using gTTS playback)
"""

import os
import time
import glob
import subprocess
import json

import speech_recognition as sr
from gtts import gTTS
import requests

# optional LLM backend - may raise if not installed or model missing
try:
    from llama_cpp import Llama
except Exception:
    Llama = None

# dotenv for API key management
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; users can set env vars manually
    pass

# Optional offline TTS fallback
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
        # Core audio and command settings
        self.recognizer = None
        self.mic = None
        self.commands_dir = commands_dir

        # Gemini API key is loaded from environment for safety
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")  # set GEMINI_API_KEY in .env

        # Local LLM settings
        self.model_path = model_path
        self.use_local_llm = use_local_llm and (Llama is not None)
        self.llm = None

        # Attempt to initialize local LLM if requested and available
        if self.use_local_llm:
            if os.path.exists(self.model_path):
                try:
                    print(f"[LLM] Loading local model from: {self.model_path}")
                    # instantiate once and reuse
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
    def initialize(self, mic_index: int = 0):
        """Initialize microphone and recognizer (call once)."""
        print("[Core] Booting Shibu...")

        try:
            self.recognizer = sr.Recognizer()
            self.mic = sr.Microphone(device_index=mic_index)
            print("[Audio] Microphone initialized successfully.")
        except Exception as e:
            print(f"[Error] Mic init failed: {e}")
            self.recognizer = None
            self.mic = None

        self.speak("Hello, I am Shibu. Ready to assist you!")

    # ---------------- Speech Output ----------------
    def speak(self, text: str):
        """Speak text using gTTS (online). If that fails, fallback to pyttsx3."""
        print(f"[Shibu says] {text}")
        # Try gTTS first (needs internet)
        try:
            tts = gTTS(text=text, lang="en")
            filename = "shibu_voice.mp3"
            tts.save(filename)

            # Try to play with mpg123 (fast, common on Linux). If not present, try system default player.
            try:
                subprocess.run(["mpg123", "-q", filename], check=True)
            except FileNotFoundError:
                # mpg123 not available — try platform default
                if os.name == "nt":
                    # Windows
                    os.startfile(filename)
                else:
                    # macOS / Linux fallback — try vlc or aplay
                    try:
                        subprocess.run(["vlc", "--intf", "dummy", filename], check=False)
                    except Exception:
                        try:
                            subprocess.run(["aplay", filename], check=False)
                        except Exception:
                            # give up — file exists but can't play
                            print("[TTS] Could not play MP3 with common players.")
            # remove mp3 file
            try:
                os.remove(filename)
            except Exception:
                pass
            return
        except Exception as e:
            print(f"[TTS] gTTS failed: {e}")

        # fallback to pyttsx3 (offline) if available
        if pyttsx3 is not None:
            try:
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                return
            except Exception as e:
                print(f"[TTS] pyttsx3 failed: {e}")

        # as a last resort, just print
        print("[TTS] No TTS available. Please install 'gtts' or 'pyttsx3' for voice output.")

    # ---------------- Speech Input ----------------
    def listen(self, phrase_time_limit: int = 5):
        """Listen for user speech and return recognized text (lower-cased)."""
        if not self.recognizer or not self.mic:
            print("[Error] Speech recognizer not initialized.")
            return None

        with self.mic as source:
            print("[Audio] Listening...")
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            except Exception:
                pass
            audio = None
            try:
                audio = self.recognizer.listen(source, phrase_time_limit=phrase_time_limit)
            except Exception as e:
                print(f"[Audio] Listen failed: {e}")
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
        """Main decision pipeline for the recognized command text."""
        if not command:
            return

        print(f"[Command] Received: {command}")
        # 1. Exact/local filename match
        file_path = self.find_local_command(command)

        if file_path:
            self.speak(f"Executing task for {command}")
            self.execute_file(file_path)
            return

        # 2. Try local LLM (if available) to infer best match
        self.speak("I couldn't find an exact match. Checking patterns...")
        predicted_path = self.query_local_llm(command)

        if predicted_path:
            self.speak(f"I found something similar: {os.path.basename(predicted_path)}. Executing.")
            self.execute_file(predicted_path)
            return

        # 3. Gemini fallback if available
        self.speak("Let me check with Gemini before proceeding.")
        feasible = self.query_gemini(command)

        if feasible:
            self.speak("Gemini confirmed feasibility. No local file found though.")
            # Optionally: you can implement a safe default action here,
            # or ask the user for confirmation via voice and then execute a safe script.
        else:
            self.speak("Gemini suggests not executing this command.")

    # ---------------- File Search ----------------
    def find_local_command(self, command: str):
        """Search for a file in the commands directory that matches the spoken command.

        Strategy:
        - convert spaces to underscores and search for files containing that pattern
        - case-insensitive
        """
        # create commands dir if missing so user sees it
        if not os.path.exists(self.commands_dir):
            print(f"[File] Commands directory '{self.commands_dir}' does not exist.")
            return None

        pattern = command.strip().lower().replace(" ", "_")
        # Try exact-like matches first
        files = glob.glob(os.path.join(self.commands_dir, f"*{pattern}*"))
        if files:
            print(f"[File] Found exact-ish match: {files[0]}")
            return files[0]

        # Fallback: check each filename tokens
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
        """Execute a local file (Python script or other)."""
        try:
            if path.endswith(".py"):
                print(f"[Execute] Running python script: {path}")
                # use subprocess.run for safety and to capture output
                subprocess.run(["python3", path], check=False)
            else:
                # for other executables: try to run directly
                print(f"[Execute] Running command/file: {path}")
                subprocess.run([path], check=False)
        except Exception as e:
            self.speak(f"Error executing {path}: {e}")

    # ---------------- Local LLM (TinyDolphin / Gemma) ----------------
    def query_local_llm(self, command: str):
        """
        If a local LLM is available (self.llm), ask it to pick the best filename.
        Otherwise, fall back to a simple filename pattern match (already done in find_local_command).
        """
        try:
            available_files = [os.path.basename(f) for f in glob.glob(os.path.join(self.commands_dir, "*"))]
            if not available_files:
                print("[LLM] No files in commands directory to compare.")
                return None

            # If local LLM is not available, try a smarter filename-token match
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

            # Prepare a concise prompt for the local model
            prompt = (
                f"You are a helper that maps user intent to filenames. "
                f"User said: '{command}'.\n"
                f"Available filenames: {available_files}\n"
                f"Reply only with a single filename from the list that best matches the intent."
            )

            # Call the local model
            print("[LLM] Querying local model for best match...")
            # llama_cpp typically accepts llm(prompt, max_tokens=...)
            out = self.llm(prompt, max_tokens=64)
            # output format can vary; attempt to parse
            text = ""
            if isinstance(out, dict):
                # new API returns choices list with 'text' or 'message'
                choices = out.get("choices", [])
                if choices:
                    text = choices[0].get("text") or choices[0].get("message", {}).get("content", "")
                else:
                    text = out.get("text", "")
            else:
                # fallback to string
                text = str(out)

            if not text:
                print("[LLM] Model returned empty response.")
                return None

            # sanitize and try to match one of the available filenames
            candidate = text.strip().splitlines()[0].strip().strip('"').strip("'")
            print(f"[LLM] Model candidate: '{candidate}'")

            # If the model returned a plain filename that exists, use it
            if candidate in available_files:
                return os.path.join(self.commands_dir, candidate)

            # Try case-insensitive and partial matches
            for fname in available_files:
                if candidate.lower() in fname.lower():
                    return os.path.join(self.commands_dir, fname)

            # If model returned a word phrase, try token match
            candidate_tokens = [t for t in candidate.replace(".", " ").replace("_", " ").split() if len(t) > 2]
            best_score = 0
            best_file = None
            for fname in available_files:
                score = sum(1 for t in candidate_tokens if t in fname.lower())
                if score > best_score:
                    best_score = score
                    best_file = fname
            if best_score > 0:
                return os.path.join(self.commands_dir, best_file)

            print("[LLM] No usable match from model output.")
            return None

        except Exception as e:
            print(f"[LLM Error] {e}")
            return None

    # ---------------- Gemini Fallback ----------------
    def query_gemini(self, command: str) -> bool:
        """Query Gemini for a feasibility / safety check. Returns True if Gemini indicates 'safe/yes'."""
        if not self.gemini_api_key:
            print("[Gemini] No Gemini API key provided (set GEMINI_API_KEY in .env). Skipping.")
            return False

        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": self.gemini_api_key}
            data = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    f"You are an assistant that determines whether the following user command "
                                    f"is safe and feasible to execute by a local robot: '{command}'.\n"
                                    "Answer concisely and include either the word 'SAFE' or 'UNSAFE' at the start of your answer."
                                )
                            }
                        ]
                    }
                ]
            }
            response = requests.post(url, headers=headers, params=params, json=data, timeout=15)
            result = response.json()
            # Try to extract textual reply robustly
            text = ""
            try:
                candidates = result.get("candidates", [])
                if candidates:
                    # Some Gemini responses include 'content': {'parts': [ { 'text': '...' }]}
                    text = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
                else:
                    # fallback: try other keys
                    text = json.dumps(result)
            except Exception:
                text = str(result)

            print("[Gemini Response]", text[:400])
            text_lower = (text or "").lower()
            if "safe" in text_lower or text_lower.strip().startswith("safe"):
                return True
            if "unsafe" in text_lower or text_lower.strip().startswith("unsafe"):
                return False
            # fallback heuristic
            if any(k in text_lower for k in ("yes", "ok", "doable", "feasible")):
                return True
            return False
        except Exception as e:
            print(f"[Gemini Error] {e}")
            return False

    # ---------------- Main Loop ----------------
    def run(self):
        """Continuous listening and handling loop."""
        try:
            while True:
                command = self.listen()
                if command:
                    self.handle_command(command)
                # small pause to avoid tight loop if microphone issues
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n[Core] Shutting down.")
            self.speak("Goodbye!")
            time.sleep(1)
            print("[Core] Shutdown complete.")


# ----------------- Helper: microphone index listing (run separately if needed) -----------------
def list_microphones():
    """Utility to print available microphone indices if you need to change device_index."""
    try:
        for i, name in enumerate(sr.Microphone.list_microphone_names()):
            print(i, name)
    except Exception as e:
        print("Could not list microphones:", e)


# ----------------- Entrypoint -----------------
if __name__ == "__main__":
    # If you need to check mic indexes, uncomment below:
    # list_microphones(); raise SystemExit(0)

    shibu = ShibuCore()
    # optionally change the mic index if you know your device is not 0
    shibu.initialize(mic_index=0)
    shibu.run()
