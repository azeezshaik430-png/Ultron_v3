"""
ULTRON V3
Speech Input System
Sounddevice / SpeechRecognition Microphone Handler
"""

import sounddevice as sd
import speech_recognition as sr
import scipy.io.wavfile as wav
import tempfile
import os
import time
import threading
from core.logger import logger
from core.config import config

# Global Speech Recognizer Configuration
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.pause_threshold = 0.8

_calibrated = False
_calibration_lock = threading.Lock()
_interruption_stop_fn = None
_interruption_lock = threading.Lock()


def calibrate_ambient_noise(source, duration=0.5, force=False):
    """Perform lazy one-time ambient-noise calibration and cache energy threshold."""
    global _calibrated
    with _calibration_lock:
        if not _calibrated or force:
            t_start = time.perf_counter()
            recognizer.adjust_for_ambient_noise(source, duration=duration)
            _calibrated = True
            calib_ms = (time.perf_counter() - t_start) * 1000.0
            logger.info(
                f"[SpeechInput] Ambient noise calibrated in {calib_ms:.2f} ms | "
                f"Energy Threshold: {recognizer.energy_threshold:.2f}"
            )


def _interruption_callback(recognizer_instance, audio):
    from voice.speech_output import speaking, stop_speaking
    if not speaking():
        return
        
    logger.info("[VoiceInterrupt] Audio captured")
    try:
        text = recognizer_instance.recognize_google(audio, language="en-IN").lower()
        interrupt_phrases = ["stop", "wait", "quiet", "shut up", "pause", "ultron stop"]
        
        # Must exactly match one of the phrases, or contain it
        if any(p in text for p in interrupt_phrases):
            logger.info(f"[VoiceInterrupt] Phrase detected: '{text}'")
            logger.info("[VoiceInterrupt] INTERRUPTION_TRIGGERED")
            logger.info("[VoiceOutput] TTS_STOP_REQUESTED")
            stop_speaking()
    except Exception:
        pass


def start_interruption_listener():
    global _interruption_stop_fn
    with _interruption_lock:
        if _interruption_stop_fn is not None:
            return
            
        logger.info("[VoiceInterrupt] Listener started")
        try:
            m = sr.Microphone()
            _interruption_stop_fn = recognizer.listen_in_background(m, _interruption_callback, phrase_time_limit=3)
        except Exception as e:
            logger.error(f"[VoiceInterrupt] Failed to start listener: {e}")


def stop_interruption_listener():
    global _interruption_stop_fn
    with _interruption_lock:
        if _interruption_stop_fn is not None:
            try:
                _interruption_stop_fn(wait_for_stop=True)
            except Exception as exc:
                logger.debug(f"[VoiceInterrupt] Stop notice: {exc}")
            _interruption_stop_fn = None


def listen(silent=False):
    from voice.speech_output import speaking

    # CRITICAL: release the interruption-listener mic handle first.
    # start_interruption_listener() (called inside speak()) opens sr.Microphone()
    # in a background thread. If we attempt to open a second Microphone stream
    # while that background thread is still holding the device, PyAudio on Windows
    # blocks or silently fails. Stopping the listener here guarantees the device
    # is free before we try to record.
    stop_interruption_listener()

    # Do not record while speaking if we are handling it in background
    if speaking():
        time.sleep(0.5)
        return ""

    if not silent:
        logger.info("Listening Boss...")

    t_listen_start = time.perf_counter()

    try:
        if not silent:
            logger.info("Speak Boss...")

        m = sr.Microphone()
        with m as source:
            calibrate_ambient_noise(source, duration=0.5)
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                if not silent:
                    logger.debug("[SpeechInput] Listen timeout: No speech detected within timeout window (5s)")
                return ""

        t_stt_start = time.perf_counter()
        text = recognizer.recognize_google(
            audio,
            language="en-IN"
        )
        stt_latency_ms = (time.perf_counter() - t_stt_start) * 1000.0
        total_listen_latency_ms = (time.perf_counter() - t_listen_start) * 1000.0
        logger.info(
            f"[Instrumentation] stt_latency_ms: {stt_latency_ms:.2f} ms | "
            f"total_listen_latency_ms: {total_listen_latency_ms:.2f} ms | "
            f"energy_threshold: {recognizer.energy_threshold:.2f}"
        )
        
        text_lower = text.lower().strip()
            
        if not silent:
            logger.info(f"You said: {text}")
        return text_lower

    except sr.UnknownValueError:
        if not silent:
            logger.info("[SpeechInput] Didn't understand Boss (STT UnknownValueError)")
        return ""

    except sr.RequestError as e:
        if not silent:
            logger.warning(f"[SpeechInput] Speech service unavailable (STT RequestError: {e})")
        return ""

    except KeyboardInterrupt:
        logger.info("Voice input stopped by user")
        return ""

    except Exception as e:
        logger.error(f"[SpeechInput] Voice Error: {type(e).__name__}: {e}")
        return ""


if __name__ == "__main__":
    while True:
        command = listen()
        if command:
            logger.info(f"Command: {command}")