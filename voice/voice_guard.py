"""
ULTRON V3
Boss Voice Guard
Preloaded & Cached VoiceEncoder Engine with Multi-Segment Embedding Averaging
Threshold: 0.68
"""

import os
import threading
import time
from pathlib import Path
from typing import Optional
import numpy as np
from core.logger import logger

BOSS_VOICE = "voice/samples/boss_voice.wav"
THRESHOLD = 0.68

_encoder_instance = None
_cached_boss_embed: Optional[np.ndarray] = None
_cached_boss_mtime: float = 0.0
_preload_thread: Optional[threading.Thread] = None


def _get_encoder():
    """Initialization helper for Resemblyzer VoiceEncoder."""
    global _encoder_instance
    if _encoder_instance is None:
        logger.info("[VoiceGuard] Initializing VoiceEncoder neural network...")
        t0 = time.perf_counter()
        from resemblyzer import VoiceEncoder
        _encoder_instance = VoiceEncoder()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(f"[VoiceGuard] VoiceEncoder neural model loaded in {elapsed_ms:.2f} ms.")
    return _encoder_instance


def preload_voice_guard() -> None:
    """
    Preload VoiceEncoder neural model and Boss voice embedding asynchronously in a background daemon thread during application startup.
    Eliminates first-verification model loading latency.
    """
    global _preload_thread
    if _preload_thread is None:
        def _target():
            t_start = time.perf_counter()
            logger.info("[VoiceGuard] Preloading VoiceEncoder in background thread...")
            try:
                _get_encoder()
                if os.path.exists(BOSS_VOICE):
                    _get_boss_embedding()
                elapsed = (time.perf_counter() - t_start) * 1000.0
                logger.info(f"[VoiceGuard] Preloading completed in {elapsed:.2f} ms.")
            except Exception as e:
                logger.error(f"[VoiceGuard] Background preloading error: {e}")

        _preload_thread = threading.Thread(target=_target, daemon=True, name="VoiceGuardPreloader")
        _preload_thread.start()


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


def _get_boss_embedding() -> Optional[np.ndarray]:
    """Retrieve or compute cached Boss voice embedding with file mtime validation."""
    global _cached_boss_embed, _cached_boss_mtime
    if not os.path.exists(BOSS_VOICE):
        return None

    mtime = os.path.getmtime(BOSS_VOICE)
    if _cached_boss_embed is not None and mtime == _cached_boss_mtime:
        return _cached_boss_embed

    logger.info("[VoiceGuard] Computing and caching Boss voice reference embedding...")
    t0 = time.perf_counter()
    _cached_boss_embed = _get_average_embedding(BOSS_VOICE)
    _cached_boss_mtime = mtime
    elapsed = (time.perf_counter() - t0) * 1000.0
    logger.info(f"[VoiceGuard] Boss voice reference embedding cached in {elapsed:.2f} ms.")
    return _cached_boss_embed


def verify_boss(test_voice: str) -> bool:
    """Verify speaker against registered boss_voice.wav with telemetry performance tracking."""
    from core.config import config
    if not getattr(config, "VOICE_AUTH_ENABLED", True):
        logger.warning("[VoiceGuard] ⚠️ [DEV MODE] Voice authentication bypassed via VOICE_AUTH_ENABLED=false.")
        return True

    t_start = time.perf_counter()
    if not os.path.exists(BOSS_VOICE):
        logger.warning("Boss voice sample missing! Prompting voice registration...")
        from voice.voice_auth import register_voice
        register_voice()
        if not os.path.exists(BOSS_VOICE):
            logger.error("Voice registration failed or cancelled. Access Denied.")
            return False

    try:
        t_embed_start = time.perf_counter()
        boss_embed = _get_boss_embedding()
        if boss_embed is None:
            logger.error("Failed to load Boss voice embedding.")
            return False

        test_embed = _get_average_embedding(test_voice)
        t_embed_end = time.perf_counter()

        score = float(
            np.dot(boss_embed, test_embed)
            / (np.linalg.norm(boss_embed) * np.linalg.norm(test_embed))
        )

        total_verify_ms = (t_embed_end - t_start) * 1000.0
        embed_calc_ms = (t_embed_end - t_embed_start) * 1000.0

        logger.info(
            f"[VoiceGuard Telemetry] Voice Match Score: {round(score, 3)} (Threshold: {THRESHOLD}) | "
            f"Verification Time: {total_verify_ms:.2f} ms (Embedding Calc: {embed_calc_ms:.2f} ms)"
        )

        if score >= THRESHOLD:
            logger.info("Boss Voice Verified successfully.")
            return True
        else:
            logger.warning("Voice verification score below threshold. Access Denied.")
            return False

    except Exception as e:
        logger.error(f"Voice Guard verification error: {e}")
        return False