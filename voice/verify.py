"""
ULTRON V3
Boss Voice Verification Module
"""

from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
import numpy as np


BOSS_VOICE = "voice/samples/boss_voice.wav"


def verify_boss(test_voice):

    encoder = VoiceEncoder()

    boss_wav = preprocess_wav(
        Path(BOSS_VOICE)
    )

    test_wav = preprocess_wav(
        Path(test_voice)
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


    print(
        "Voice Match Score:",
        round(score,3)
    )


    if score >= 0.70:
        return True

    return False