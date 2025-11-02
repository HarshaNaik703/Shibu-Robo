"""
Shibu: The AI Robot Core (Main Brain)
Runs on Raspberry Pi 4.

Hardware:
 - Mic: listens for voice commands
 - OLED: displays emotion
 - Speaker: talks via eSpeak
 - Arduino: controls motion
 - Gemini: answers general questions
"""

import os, time, json, threading, requests, serial
import speech_recognition as sr
import google.generativeai as genai
import pyttsx3
from dotenv import load_dotenv
from shibu_display import ShibuDisplay

# ------------------ 1. CONFIGURATION ------------------

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OLLAMA_ENDPOINT = "http://localhost:11434/api/chat"
TINYLAMA_MODEL = "tinyllama"

ARDUINO_PORT = "/dev/ttyACM0"
ARDUINO_BAUD = 9600
arduino = None

recognizer = None
microphone = None
display = ShibuDisplay()

# ------------------ 2. TEXT TO SPEECH ------------------

engine = None

def initialize_tts():
    """Initialize eSpeak via pyttsx3."""
    global engine
    try:
        engine = pyttsx3.init(driverName='espeak')
        engine.setProperty('rate', 160)
        voices = engine.getProperty('voices')
        # pick a safe English voice
        for v in voices:
            if "english" in v.name.lower():
                engine.setProperty('voice', v.id)
                break
        print("[Core] eSpeak initialized successfully.")
    except Exception as e:
        print(f"[Error] Could not initialize pyttsx3: {e}")
        engine = None

def speak(text):
    """Speak asynchronously using eSpeak."""
    def _thread(text):
        if not engine:
            print("[Error] No TTS engine initialized.")
            return
        try:
            print(f"Shibu says: {text}")
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"[Error] TTS failed: {e}")
    threading.Thread(target=_thread, args=(text,)).start()

# ------------------ 3. SPEECH RECOGNITION ------------------

def initialize_speech_recognition():
    global recognizer, microphone
    try:
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        with microphone as source:
            print("[Core] Calibrating mic...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[Core] Microphone ready.")
    except Exception as e:
        print(f"[Error] Mic init failed: {e}")

def listen_from_mic():
    if not recognizer or not microphone:
        print("[Error] Speech recognizer not initialized.")
        return ""
    print("\n[Ears] Listening...")
    display.show_emotion("listening")
    with microphone as source:
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            display.show_emotion("concentration")
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
            speak("Speech service error.")
            return ""

# ------------------ 4. ARDUINO ------------------

def initialize_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
        time.sleep(2)
        print(f"[Core] Arduino connected at {ARDUINO_PORT}")
    except Exception as e:
        print(f"[Warn] Arduino not connected: {e}")
        arduino = None

def send_to_arduino(cmd):
    if arduino and arduino.is_open:
        try:
            arduino.write(cmd.encode())
            print(f"[Body] Sent '{cmd}' to Arduino")
        except Exception as e:
            print(f"[Error] Arduino write failed: {e}")
    else:
        print(f"[Sim-Body] Would send '{cmd}'")

# ------------------ 5. AI BRAIN ------------------

TINYLAMA_SYSTEM_PROMPT = """
You are the brain of a robot named 'Shibu'.
Convert a voice command into structured JSON.

Actions: ['celebrate','move_forward','move_backward',
'turn_left','turn_right','stop_all','chat','find_object','error']

Respond ONLY with JSON.
"""

def get_intent_from_tinylama(user_text):
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
        r = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()['message']['content']
        return json.loads(data)
    except Exception as e:
        print(f"[Error] TinyLLaMA failed: {e}")
        return {"action":"error","data":str(e)}

def get_chat_from_gemini(prompt):
    if not GEMINI_API_KEY:
        return "My cloud brain is offline."
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        print(f"[Error] Gemini API: {e}")
        return "I had trouble reaching Gemini."

# ------------------ 6. ACTIONS ------------------

def do_celebrate(_=None):
    speak("Woohoo! I am celebrating!")
    display.show_emotion("admiration")
    send_to_arduino('c')
    time.sleep(3)
    display.show_emotion("neutral")

def do_move_forward(_=None):
    speak("Moving forward.")
    display.show_emotion("determination")
    send_to_arduino('f')

def do_move_backward(_=None):
    speak("Moving backward.")
    display.show_emotion("focused")
    send_to_arduino('b')

def do_turn_left(_=None):
    speak("Turning left.")
    display.show_emotion("neutral")
    send_to_arduino('l')

def do_turn_right(_=None):
    speak("Turning right.")
    display.show_emotion("neutral")
    send_to_arduino('r')

def do_stop_all(_=None):
    speak("Stopping all movement.")
    display.show_emotion("neutral")
    send_to_arduino('s')

def do_find_object(target):
    speak(f"Scanning for {target or 'something'}...")
    display.show_emotion("curiosity")
    time.sleep(1)
    speak("Sorry, I cannot see objects yet.")
    display.show_emotion("sadness")

def do_chat(prompt):
    speak("Let me think...")
    display.show_emotion("concentration")
    answer = get_chat_from_gemini(prompt)
    speak(answer)
    display.show_emotion("satisfaction")

def do_unknown(_=None):
    speak("I didn't understand that.")
    display.show_emotion("confusion")

ACTION_ROUTER = {
    "celebrate": do_celebrate,
    "move_forward": do_move_forward,
    "move_backward": do_move_backward,
    "turn_left": do_turn_left,
    "turn_right": do_turn_right,
    "stop_all": do_stop_all,
    "find_object": do_find_object,
    "chat": do_chat,
    "error": do_unknown
}

# ------------------ 7. MAIN LOOP ------------------

def main():
    print("[Core] Booting Shibu...")
    initialize_tts()
    initialize_speech_recognition()
    initialize_arduino()
    display.initialize()

    speak("Shibu is online and ready!")

    while True:
        try:
            cmd = listen_from_mic()
            if not cmd:
                continue
            intent = get_intent_from_tinylama(cmd)
            action = intent.get("action","error")
            data = intent.get("data")
            func = ACTION_ROUTER.get(action, do_unknown)
            if func in [do_chat, do_find_object]:
                func(data)
            else:
                func()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Critical] {e}")
            speak("A critical error occurred.")

    print("[Core] Shutting down.")
    speak("Goodbye.")
    display.show_emotion("sleep")
    if arduino and arduino.is_open:
        send_to_arduino('s')
        arduino.close()

if __name__ == "__main__":
    main()
