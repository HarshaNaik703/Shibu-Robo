"""
Shibu: The AI Robot Core (Main Brain)
This script runs on the Raspberry Pi.

Core Logic:
1.  (Ears) Listens for voice commands.
2.  (Brain) Sends command to TinyLLaMA to get a structured JSON intent.
3.  (Router) Maps the JSON intent to a local Python function.
4.  (Action) The Python function runs multiple tasks in parallel:
    a. (Face) Tells the OLED display *what* emotion to show.
    b. (Body) Tells the Arduino *how* to move via Serial commands.
    c. (Voice) Speaks a response simultaneously.
    d. (Cloud) Calls Gemini if the action is 'chat'.
"""

import requests
import json
import threading
import time
import os
import pyttsx3
import google.generativeai as genai
import speech_recognition as sr
import serial  # To talk to Arduino

from shibu_display import ShibuDisplay
from dotenv import load_dotenv

# ✅ Load environment variables from .env
load_dotenv()

# --- 1. Configuration & Global Variables ---

# Ollama (TinyLLaMA) Configuration
OLLAMA_ENDPOINT = "http://localhost:11434/api/chat"
TINYLAMA_MODEL = "tinyllama"

# Google Gemini Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # ✅ Correct way

# Arduino Serial Configuration
ARDUINO_PORT = "/dev/ttyACM0"  # Common for Arduino Uno/Mega
ARDUINO_BAUD = 9600
arduino = None

# Global TTS Engine
tts_engine = None

# Global Speech Recognizer
recognizer = None
microphone = None

# ✅ Create global OLED display object
display = ShibuDisplay()

# System prompt for TinyLLaMA
TINYLAMA_SYSTEM_PROMPT = """
You are the central brain for a robot named 'Shibu'. Your ONLY job is to
convert a user's command into a structured JSON object.

You must choose an 'action' from this exact list:
['celebrate', 'move_forward', 'move_backward', 'turn_left', 'turn_right', 'stop_all', 'chat', 'find_object', 'error']

Respond ONLY with the JSON object.
---
User: 'Hey Shibu, do a little victory dance!'
{"action": "celebrate", "data": null}
---
User: 'go forward'
{"action": "move_forward", "data": null}
---
User: 'look for my keys'
{"action": "find_object", "data": "keys"}
---
User: 'what's the weather today?'
{"action": "chat", "data": "what's the weather today?"}
"""

# --- 2. Core Modules (Voice, Brains, Serial) ---

def initialize_tts():
    global tts_engine
    try:
        tts_engine = pyttsx3.init()
        tts_engine.setProperty('rate', 160)
        print("[Core] TTS Engine Initialized.")
    except Exception as e:
        print(f"[Error] Failed to initialize TTS engine: {e}")

def initialize_speech_recognition():
    global recognizer, microphone
    try:
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        with microphone as source:
            print("[Core] Calibrating microphone for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[Core] Microphone Initialized.")
    except Exception as e:
        print(f"[Error] Could not initialize microphone: {e}")

def initialize_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
        time.sleep(2)
        print(f"[Core] Arduino connected at {ARDUINO_PORT}.")
    except Exception as e:
        print(f"[Error] Could not connect to Arduino: {e}")
        print(f"Is it plugged in? Is the port '{ARDUINO_PORT}' correct?")
        arduino = None  # Continue in simulation mode

def send_to_arduino(command_char):
    if arduino and arduino.is_open:
        try:
            arduino.write(command_char.encode())
            print(f"[Body] Sent command '{command_char}' to Arduino.")
        except Exception as e:
            print(f"[Error] Failed to send command to Arduino: {e}")
    else:
        print(f"[Debug-Body] Would send: '{command_char}'")

def listen_from_mic():
    if not recognizer or not microphone:
        print("[Error] Speech recognizer not initialized.")
        time.sleep(2)
        return ""

    print("\n[Ears] Listening for command...")
    display.show_emotion("listening")

    with microphone as source:
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            display.show_emotion("concentration")
            print("[Ears] Recognizing...")
            text = recognizer.recognize_google(audio)
            print(f"You said: '{text}'")
            return text.lower()
        except sr.WaitTimeoutError:
            display.show_emotion("neutral")
            return ""
        except sr.UnknownValueError:
            display.show_emotion("confusion")
            speak("Sorry, I didn't catch that.")
            return ""
        except sr.RequestError:
            display.show_emotion("sadness")
            speak("My connection to the speech service failed.")
            return ""

def speak(text_to_speak):
    if not tts_engine:
        print("[Error] TTS Engine not initialized. Cannot speak.")
        return

    def _speak_in_thread(text):
        try:
            print(f"Shibu says: {text}")
            tts_engine.say(text)
            tts_engine.runAndWait()
        except Exception:
            pass

    threading.Thread(target=_speak_in_thread, args=(text_to_speak,)).start()

def get_intent_from_tinylama(user_text):
    print(f"[Brain] Sending to TinyLLaMA: '{user_text}'")
    payload = {
        "model": TINYLAMA_MODEL,
        "messages": [
            {"role": "system", "content": TINYLAMA_SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "format": "json",
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=20)
        response.raise_for_status()
        intent_json_str = response.json()['message']['content']
        intent = json.loads(intent_json_str)
        print(f"[Brain] TinyLLaMA Intent: {intent}")
        return intent
    except requests.exceptions.ConnectionError:
        print("[Error] Cannot connect to Ollama. Is it running?")
        return {"action": "error", "data": "Ollama connection failed"}
    except (json.JSONDecodeError, KeyError):
        print("[Error] TinyLLaMA did not return valid JSON.")
        return {"action": "error", "data": "AI brain failed to format"}
    except Exception as e:
        print(f"[Error] Unknown Ollama/Request error: {e}")
        return {"action": "error", "data": str(e)}

def get_chat_from_gemini(prompt):
    print("[Brain] Sending to Gemini API...")
    if not GEMINI_API_KEY:
        print("[Warn] GEMINI_API_KEY not set. Chat fallback is offline.")
        return "I can't answer that right now, my cloud connection is offline."
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[Error] Gemini API failed: {e}")
        return "I had a problem trying to look that up."

# --- 3. Hardware STUBS (Vision) ---

def get_image_from_camera():
    print("  [Camera] Capturing image...")
    time.sleep(1)
    return "fake_image_data"

def detect_objects(image):
    print(f"  [Vision] Detecting objects in {image}...")
    time.sleep(1)
    return ["a cup", "a keyboard"]

# --- 4. The "Action Library" ---

def do_celebrate(data=None):
    print("\n[Action] Executing: 'celebrate'")
    speak("Woohoo! I am celebrating!")
    display.show_emotion("admiration")
    send_to_arduino('c')
    time.sleep(3)
    display.show_emotion("neutral")

def do_move_forward(data=None):
    print("\n[Action] Executing: 'move_forward'")
    speak("Moving forward.")
    display.show_emotion("determination")
    send_to_arduino('f')

def do_move_backward(data=None):
    print("\n[Action] Executing: 'move_backward'")
    speak("Moving backward.")
    display.show_emotion("focused")
    send_to_arduino('b')

def do_turn_left(data=None):
    print("\n[Action] Executing: 'turn_left'")
    speak("Turning left.")
    display.show_emotion("neutral")
    send_to_arduino('l')

def do_turn_right(data=None):
    print("\n[Action] Executing: 'turn_right'")
    speak("Turning right.")
    display.show_emotion("neutral")
    send_to_arduino('r')

def do_stop_all(data=None):
    print("\n[Action] Executing: 'stop_all'")
    speak("Stopping all movement.")
    display.show_emotion("neutral")
    send_to_arduino('s')

def do_find_object(target_object):
    if not target_object:
        target_object = "anything"

    print(f"\n[Action] Executing: 'find_object' with data: '{target_object}'")
    speak(f"Okay, I am scanning the room for {target_object}.")
    display.show_emotion("curiosity")

    image = get_image_from_camera()
    found_objects = detect_objects(image)

    if target_object == "anything" and found_objects:
        speak(f"I see {', '.join(found_objects)}.")
        display.show_emotion("joy")
    elif target_object in found_objects:
        speak(f"Success! I have found the {target_object}.")
        display.show_emotion("joy")
    else:
        speak(f"Sorry, I looked but I do not see the {target_object}.")
        display.show_emotion("sadness")

def do_chat(prompt):
    print(f"\n[Action] Executing: 'chat' with data: '{prompt}'")
    speak("Hmm, let me think about that...")
    display.show_emotion("concentration")

    answer = get_chat_from_gemini(prompt)
    speak(answer)
    display.show_emotion("satisfaction")

def do_unknown_action(data=None):
    print(f"\n[Action] Executing: 'error / unknown'")
    speak("I'm sorry, that is not a feasible action or I didn't understand.")
    display.show_emotion("confusion")

# --- 5. Action Router ---

ACTION_ROUTER = {
    "celebrate": do_celebrate,
    "move_forward": do_move_forward,
    "move_backward": do_move_backward,
    "turn_left": do_turn_left,
    "turn_right": do_turn_right,
    "stop_all": do_stop_all,
    "find_object": do_find_object,
    "chat": do_chat,
    "error": do_unknown_action
}

# --- 6. Main Program Loop ---

def main():
    print("[Core] Shibu is booting up...")

    initialize_tts()
    initialize_speech_recognition()
    initialize_arduino()
    display.initialize()

    if not GEMINI_API_KEY:
        print("="*30)
        print("[WARN] GEMINI_API_KEY is not set. Chat fallback will not work.")
        print("Set it with: export GEMINI_API_KEY='your_key'")
        print("="*30)

    speak("Shibu is online and ready.")

    while True:
        try:
            user_text = listen_from_mic()
            if not user_text:
                continue

            intent_json = get_intent_from_tinylama(user_text)
            action_name = intent_json.get("action")
            action_data = intent_json.get("data")

            action_function = ACTION_ROUTER.get(action_name, do_unknown_action)

            if action_function in [do_find_object, do_chat]:
                action_function(action_data)
            else:
                action_function()

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Main loop failed: {e}")
            try:
                speak("A critical error occurred. Please check my console.")
            except:
                pass
            time.sleep(2)

    print("\n[Core] Shibu is shutting down.")
    speak("Shibu is shutting down. Goodbye.")
    display.show_emotion("sleep")

    if arduino and arduino.is_open:
        send_to_arduino('s')
        arduino.close()

if __name__ == "__main__":
    main()
