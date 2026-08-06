import sounddevice as sd

print("Available microphones:")

print(sd.query_devices())


print("Testing mic...")

duration = 5

recording = sd.rec(
    int(duration * 44100),
    samplerate=44100,
    channels=1
)

sd.wait()

print("Mic working Boss!")