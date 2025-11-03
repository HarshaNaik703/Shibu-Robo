import speech_recognition as sr

mics = sr.Microphone.list_microphone_names()
if not mics:
    print("❌ No microphones detected by Python.")
else:
    print("✅ Detected microphones:")
    for i, name in enumerate(mics):
        print(f"{i}: {name}")
