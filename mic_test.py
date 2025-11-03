import speech_recognition as sr

r = sr.Recognizer()
mic = sr.Microphone(device_index=0)

print("Listening test started...")
with mic as source:
    r.adjust_for_ambient_noise(source, duration=2)
    print("Say something...")
    audio = r.listen(source, phrase_time_limit=5)
    print("Captured audio!")
