import sounddevice as sd

print("ULTRON MIC TEST")

print("\nAvailable Devices:\n")
print(sd.query_devices())

print("\nRecording started... Speak Boss!")

duration = 5
samplerate = 44100

recording = sd.rec(
    int(duration * samplerate),
    samplerate=samplerate,
    channels=1
)

sd.wait()

print("\nMic working Boss! ✅")