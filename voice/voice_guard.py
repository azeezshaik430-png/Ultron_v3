"""
ULTRON V3
Boss Voice Guard
Lazy Initialized VoiceEncoder Engine with Multi-Segment Embedding Averaging
Threshold: 0.68 - 0.70
"""

import os
import numpy as np
from pathlib import Path
from core.logger import logger

BOSS_VOICE = "voice/samples/boss_voice.wav"
THRESHOLD = 0.68

_encoder_instance = None


def _get_encoder():
    """Lazy initialization helper for Resemblyzer VoiceEncoder."""
    global _encoder_instance
    if _encoder_instance is None:
        logger.info("Lazily initializing VoiceEncoder neural network for first verification...")
        from resemblyzer import VoiceEncoder
        _encoder_instance = VoiceEncoder()
    return _encoder_instance


def _get_average_embedding(wav_path: str) -> np.ndarray:
    """Load audio, preprocess, and compute averaged embedding across segments."""
    from resemblyzer import preprocess_wav

    encoder = _get_encoder()
    wav = preprocess_wav(Path(wav_path))
    sampling_rate = 16000
    segment_len = int(1.5 * sampling_rate)

    if len(wav) > segment_len:
        segments = []
        step = int(0.75 * sampling_rate)
        for start in range(0, len(wav) - segment_len + 1, step):
            sub_wav = wav[start : start + segment_len]
            embed = encoder.embed_utterance(sub_wav)
            segments.append(embed)
        if segments:
            avg_embed = np.mean(segments, axis=0)
            return avg_embed / np.linalg.norm(avg_embed)

    full_embed = encoder.embed_utterance(wav)
    return full_embed / np.linalg.norm(full_embed)


def verify_boss(test_voice: str) -> bool:
    """Verify speaker against registered boss_voice.wav."""
    if not os.path.exists(BOSS_VOICE):
        logger.warning("Boss voice sample missing! Prompting voice registration...")
        from voice.voice_auth import register_voice
        register_voice()
        if not os.path.exists(BOSS_VOICE):
            logger.error("Voice registration failed or cancelled. Access Denied.")
            return False

    try:
        boss_embed = _get_average_embedding(BOSS_VOICE)
        test_embed = _get_average_embedding(test_voice)

        score = float(
            np.dot(boss_embed, test_embed)
            / (np.linalg.norm(boss_embed) * np.linalg.norm(test_embed))
        )

        logger.info(f"Voice Match Score: {round(score, 3)} (Threshold: {THRESHOLD})")

        if score >= THRESHOLD:
            logger.info("Boss Voice Verified successfully.")
            return True
        else:
            logger.warning("Voice verification score below threshold. Access Denied.")
            return False

    except Exception as e:
        logger.error(f"Voice Guard verification error: {e}")
        return False