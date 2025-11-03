#!/usr/bin/env python3
"""
setup_check.py — Environment setup checker for Shibu-Robo
----------------------------------------------------------
Checks:
- Folder structure
- Gemini API key
- Microphone device
- Python dependencies
- Local model file
- Audio player
"""

import os
import importlib
import shutil
import sys


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_pass(msg):
    print(f"{Color.GREEN}[PASS]{Color.RESET} {msg}")


def print_fail(msg):
    print(f"{Color.RED}[FAIL]{Color.RESET} {msg}")


def print_info(msg):
    print(f"{Color.BLUE}[INFO]{Color.RESET} {msg}")


def print_warn(msg):
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")


# ---------------- FOLDER CHECK ----------------
def check_folders():
    required = ["commands", "models"]
    ok = True
    for folder in required:
        if os.path.exists(folder):
            print_pass(f"'{folder}/' directory found.")
        else:
            print_fail(f"'{folder}/' directory missing.")
            ok = False
    return ok


# ---------------- GEMINI API CHECK ----------------
def check_gemini_api():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            print_pass("Gemini API key found in .env file.")
            return True
        else:
            print_warn("Gemini API key missing in .env file.")
            return False
    except ImportError:
        print_warn("python-dotenv not installed — skipping Gemini API check.")
        return False


# ---------------- MICROPHONE CHECK ----------------
def check_microphone():
    try:
        import speech_recognition as sr
        mics = sr.Microphone.list_microphone_names()
        if not mics:
            print_fail("No microphone detected.")
            return False
        print_pass(f"Microphones detected: {mics}")
        return True
    except Exception as e:
        print_fail(f"Microphone check failed: {e}")
        return False


# ---------------- MODEL FILE CHECK ----------------
def check_model_file():
    model_dir = "models"
    if not os.path.exists(model_dir):
        print_warn("Model directory missing.")
        return False

    ggufs = [f for f in os.listdir(model_dir) if f.endswith(".gguf")]
    if ggufs:
        print_pass(f"Local model file found: {ggufs[0]}")
        return True
    else:
        print_warn("No .gguf model found — local LLM disabled.")
        return False


# ---------------- LIBRARY CHECK ----------------
REQUIRED_LIBS = [
    "speech_recognition",
    "gtts",
    "requests",
    "python_dotenv",  # <— fixed module name for import test
    "pyttsx3",
]
OPTIONAL_LIBS = ["llama_cpp"]


def check_libraries():
    ok = True
    print_info("Checking Python dependencies...")

    LIB_MAP = {
        "speech_recognition": "speech_recognition",
        "gtts": "gtts",
        "requests": "requests",
        "python-dotenv": "dotenv",  # ← fixed import name
        "pyttsx3": "pyttsx3",
    }
    OPTIONAL_LIBS = {"llama_cpp": "llama_cpp"}

    # Required libs
    for name, module in LIB_MAP.items():
        try:
            importlib.import_module(module)
            print_pass(f"{name} is installed.")
        except ImportError:
            print_fail(f"Missing required library: {name}")
            ok = False

    # Optional libs
    for name, module in OPTIONAL_LIBS.items():
        try:
            importlib.import_module(module)
            print_pass(f"Optional library available: {name}")
        except ImportError:
            print_warn(f"Optional library not installed: {name} (for local LLM).")

    return ok



# ---------------- AUDIO PLAYER CHECK ----------------
def check_audio_player():
    if shutil.which("mpg123"):
        print_pass("mpg123 audio player found.")
        return True
    else:
        print_warn("mpg123 not found — install via: sudo apt install mpg123")
        return False


# ---------------- MAIN ----------------
def main():
    print_info("Running Shibu setup checks...\n")

    folder_ok = check_folders()
    gemini_ok = check_gemini_api()
    mic_ok = check_microphone()
    libs_ok = check_libraries()
    model_ok = check_model_file()
    audio_ok = check_audio_player()

    print("\n" + "=" * 55)
    if all([folder_ok, libs_ok, mic_ok]):
        print_pass("✅ Basic system setup looks good!")
    else:
        print_fail("❌ Some essential setup steps are missing or broken.")

    if not gemini_ok:
        print_warn("Gemini features will not work until API key is added.")
    if not model_ok:
        print_warn("Local LLM features will be skipped (optional).")

    print_info("Setup check completed.")
    print("=" * 55)


if __name__ == "__main__":
    main()
