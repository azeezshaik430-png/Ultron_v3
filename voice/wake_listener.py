"""
ULTRON V3
Wake Listener + Boss Voice Authentication
"""

from voice.speech_input import listen
from voice.wake_word import check_wake_word
from voice.voice_guard import verify_boss

import sounddevice as sd
from scipy.io.wavfile import write
import os
import time


SAMPLE_RATE = 16000
DURATION = 3

AUTH_FILE = "voice/samples/auth_test.wav"


def record_auth_voice():

    os.makedirs(
        "voice/samples",
        exist_ok=True
    )

    print()
    print("🎤 Boss, please verify your voice...")
    print("Recording starts in 2 seconds...")

    time.sleep(2)

    print("recording...")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    write(
        AUTH_FILE,
        SAMPLE_RATE,
        audio
    )

    print("saved to:",AUTH_FILE)

    print("✅ Voice recorded")

    return AUTH_FILE


def wait_for_wake_word():

    print("😴 ULTRON sleeping...")
    print("Waiting for wake word...")

    while True:

        try:

            command = listen(
                silent=True
            )

            if not command:
                continue

            command = command.lower().strip()

            if check_wake_word(command):

                print()
                print("🚀 Wake word detected")

                voice_file = record_auth_voice()

                if verify_boss(voice_file):

                    print("✅ Boss Verified 🔥")
                    return True

                else:

                    print("❌ Unknown Person")
                    print("🔒 Access Denied")
                    print("😴 Returning to sleep...\n")

                    continue

        except Exception as e:

            print("Wake Listener Error:", e)