"""
ULTRON V3
Voice Authentication Test
"""

import sounddevice as sd
from scipy.io.wavfile import write
from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
import numpy as np


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

    print("Loading Boss voice...")

    encoder = VoiceEncoder()

    boss_wav = preprocess_wav(
        Path(BOSS_VOICE)
    )

    test_wav = preprocess_wav(
        Path(TEST_VOICE)
    )


    boss_embed = encoder.embed_utterance(
        boss_wav
    )

    test_embed = encoder.embed_utterance(
        test_wav
    )


    score = np.dot(
        boss_embed,
        test_embed
    ) / (
        np.linalg.norm(boss_embed) *
        np.linalg.norm(test_embed)
    )


    print()
    print("Voice Match Score:", round(score,3))


    if score >= 0.70:

        print("✅ Boss Verified 🔥")

    else:

        print("❌ Unknown Person")


if __name__ == "__main__":

    record_test_voice()

    verify_voice()
