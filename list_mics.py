import speech_recognition as sr

print("🎤 Available microphones:")
for i, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"[{i}] {name}")
