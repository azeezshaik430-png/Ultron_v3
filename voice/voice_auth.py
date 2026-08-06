"""
ULTRON V3
Voice Authentication System
Boss Voice Register + Verify
"""

import sounddevice as sd
from scipy.io.wavfile import write, read
from resemblyzer import VoiceEncoder, preprocess_wav
import numpy as np
import os


SAMPLE_RATE = 16000
DURATION = 5

VOICE_FOLDER = "voice/samples"

BOSS_VOICE = os.path.join(
    VOICE_FOLDER,
    "boss_voice.wav"
)


encoder = VoiceEncoder()


def record_audio(filename):

    os.makedirs(
        VOICE_FOLDER,
        exist_ok=True
    )

    print("\n🎤 Say:")
    print("Hello ULTRON, this is my voice")

    input("Press Enter to start...")

    print("Recording...")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    write(
        filename,
        SAMPLE_RATE,
        audio
    )

    print("✅ Recording saved")



def register_voice():

    record_audio(BOSS_VOICE)

    print("Processing Boss voice...")

    print("✅ Boss voice registered")



def verify_voice():

    temp_file = os.path.join(
        VOICE_FOLDER,
        "verify.wav"
    )

    record_audio(temp_file)


    print("Processing verification...")


    boss_wav = preprocess_wav(
        BOSS_VOICE
    )

    test_wav = preprocess_wav(
        temp_file
    )


    boss_embed = encoder.embed_utterance(
        boss_wav
    )

    test_embed = encoder.embed_utterance(
        test_wav
    )


    similarity = np.dot(
        boss_embed,
        test_embed
    )


    print(
        "Voice Match Score:",
        similarity
    )


    if similarity > 0.75:

        print("✅ Boss verified")

        return True


    else:

        print("❌ Unknown voice")

        return False



if __name__ == "__main__":

    print("1. Register Boss Voice")
    print("2. Verify Voice")


    choice = input("Choose: ")


    if choice == "1":

        register_voice()


    elif choice == "2":

        verify_voice()