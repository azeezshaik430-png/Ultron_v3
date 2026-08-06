"""
ULTRON V3
Boss Voice Verification System
"""

import os
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path


SAMPLE_RATE = 16000
DURATION = 5

BOSS_VOICE = "voice/samples/boss_voice.wav"
TEST_VOICE = "voice/samples/test_voice.wav"


def record_test_voice():

    print("🎤 Say:")
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
        TEST_VOICE,
        SAMPLE_RATE,
        audio
    )

    print("✅ Test voice recorded")


def verify_voice():

    encoder = VoiceEncoder()

    print("Loading Boss voice...")

    boss_wav = preprocess_wav(
        Path(BOSS_VOICE)
    )

    test_wav = preprocess_wav(
        Path(TEST_VOICE)
    )


    boss_embedding = encoder.embed_utterance(
        boss_wav
    )

    test_embedding = encoder.embed_utterance(
        test_wav
    )


    similarity = np.dot(
        boss_embedding,
        test_embedding
    ) / (
        np.linalg.norm(boss_embedding) *
        np.linalg.norm(test_embedding)
    )


    print("\nVoice Match Score:", round(float(similarity), 3))


    if similarity > 0.75:

        print("✅ Boss Verified 🔥")
        return True

    else:

        print("❌ Access Denied")
        return False



if __name__ == "__main__":

    record_test_voice()

    verify_voice()