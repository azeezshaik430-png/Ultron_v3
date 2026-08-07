"""
ULTRON V3
Voice Authentication System
Shared Resemblyzer Engine with Preloaded VoiceEncoder
"""

import os
import time
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from pathlib import Path
from core.logger import logger

SAMPLE_RATE = 16000
REGISTER_DURATION = 12
VERIFY_DURATION = 5
THRESHOLD = 0.68

VOICE_FOLDER = "voice/samples"
BOSS_VOICE = os.path.join(VOICE_FOLDER, "boss_voice.wav")
TEST_VOICE = os.path.join(VOICE_FOLDER, "verify.wav")


def _get_encoder():
    """Initialization helper for Resemblyzer VoiceEncoder shared with VoiceGuard."""
    from voice.voice_guard import _get_encoder as _guard_get_encoder
    return _guard_get_encoder()


def record_audio(filename: str, duration: int, prompt_msg: str) -> None:
    os.makedirs(VOICE_FOLDER, exist_ok=True)
    logger.info(f"\n🎤 {prompt_msg}")
    logger.info("Recording...")
    # REMOVED: Unnecessary time.sleep(2) wait removed for instant response

    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    write(filename, SAMPLE_RATE, audio)
    logger.info(f"Saved recording to: {filename}")


def register_voice() -> str:
    """Record 12s reference boss voice sample."""
    prompt = (
        "Boss, please read the following sentence clearly:\n"
        "\"Hello ULTRON, I am your creator and sole operator. System access granted.\""
    )
    record_audio(BOSS_VOICE, REGISTER_DURATION, prompt)
    logger.info("Boss voice registered successfully.")
    return BOSS_VOICE


def _get_average_embedding(wav_path: str) -> np.ndarray:
    """Compute averaged embedding across audio sub-segments."""
    from resemblyzer import preprocess_wav

    encoder = _get_encoder()
    wav = preprocess_wav(Path(wav_path))
    segment_len = int(1.5 * SAMPLE_RATE)

    if len(wav) > segment_len:
        segments = []
        step = int(0.75 * SAMPLE_RATE)
        for start in range(0, len(wav) - segment_len + 1, step):
            sub_wav = wav[start : start + segment_len]
            embed = encoder.embed_utterance(sub_wav)
            segments.append(embed)
        if segments:
            avg_embed = np.mean(segments, axis=0)
            return avg_embed / np.linalg.norm(avg_embed)

    full_embed = encoder.embed_utterance(wav)
    return full_embed / np.linalg.norm(full_embed)


def verify_voice() -> bool:
    """Verify 5s sample against boss_voice.wav."""
    if not os.path.exists(BOSS_VOICE):
        logger.warning("Boss voice registration required first.")
        register_voice()
        if not os.path.exists(BOSS_VOICE):
            logger.error("No boss voice registered. Verification failed.")
            return False

    record_audio(TEST_VOICE, VERIFY_DURATION, "Speak your verification sentence...")

    boss_embed = _get_average_embedding(BOSS_VOICE)
    test_embed = _get_average_embedding(TEST_VOICE)

    score = float(
        np.dot(boss_embed, test_embed)
        / (np.linalg.norm(boss_embed) * np.linalg.norm(test_embed))
    )

    logger.info(f"Voice Match Score: {round(score, 3)} (Threshold: {THRESHOLD})")

    if score >= THRESHOLD:
        logger.info("Boss verified successfully.")
        return True
    else:
        logger.warning("Unknown voice. Access Denied.")
        return False


if __name__ == "__main__":
    print("1. Register Boss Voice (12s)")
    print("2. Verify Voice (5s)")
    choice = input("Choose: ")

    if choice == "1":
        register_voice()
    elif choice == "2":
        verify_voice()