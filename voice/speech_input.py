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

import io

# Global Speech Recognizer Configuration
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.pause_threshold = 0.5

_calibrated = False
_calibration_lock = threading.Lock()
_interruption_stop_fn = None
_interruption_lock = threading.Lock()
_last_transcript = ""
_last_transcript_time = 0.0

_whisper_model = None
_whisper_lock = threading.Lock()


def _get_whisper_model():
    """Thread-safe lazy-loaded singleton for Faster-Whisper CPU/int8 engine."""
    global _whisper_model
    if _whisper_model is None:
        with _whisper_lock:
            if _whisper_model is None:
                from faster_whisper import WhisperModel
                logger.info("[SpeechInput] Initializing Faster-Whisper STT engine (model: base, device: cpu, compute_type: int8, cpu_threads: 4)...")
                _whisper_model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
                logger.info("[SpeechInput] Faster-Whisper STT engine initialized successfully.")
    return _whisper_model


def transcribe_audio(audio: sr.AudioData) -> str:
    """
    Transcribe SpeechRecognition AudioData using Faster-Whisper CPU/int8 engine with high-performance low-latency settings.
    Returns clean lowercase transcript string or "" on error/empty audio.
    """
    try:
        model = _get_whisper_model()
        wav_bytes = audio.get_wav_data()
        bio = io.BytesIO(wav_bytes)
        t0 = time.perf_counter()
        segments, info = model.transcribe(
            bio,
            language="en",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False
        )
        text = " ".join(segment.text for segment in segments).strip().lower()
        infer_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(f"[SpeechInput] Whisper Inference: {infer_ms:.2f} ms | Text: '{text}'")
        return text
    except Exception as e:
        logger.error(f"[SpeechInput] Whisper STT error: {e}")
        return ""


def calibrate_ambient_noise(source, duration=0.3, force=False):
    """Perform lazy one-time ambient-noise calibration and cache energy threshold."""
    global _calibrated
    with _calibration_lock:
        if not _calibrated or force:
            t_start = time.perf_counter()
            recognizer.adjust_for_ambient_noise(source, duration=duration)
            # Clamp energy threshold strictly to stable operational bounds [300.0, 1200.0]
            recognizer.energy_threshold = max(300.0, min(recognizer.energy_threshold, 1200.0))
            recognizer.dynamic_energy_threshold = False  # Freeze threshold to prevent drift
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
        text = transcribe_audio(audio)
        interrupt_phrases = ["stop", "wait", "quiet", "shut up", "pause", "ultron stop"]
        
        # Must exactly match one of the phrases, or contain it
        if any(p in text for p in interrupt_phrases):
            logger.info(f"[VoiceInterrupt] Phrase detected: '{text}'")
            logger.info("[VoiceInterrupt] INTERRUPTION_TRIGGERED")
            logger.info("[VoiceOutput] TTS_STOP_REQUESTED")
            stop_speaking()
    except Exception:
        pass


_active_mic_count = 0
_mic_count_lock = threading.Lock()


def is_interruption_listener_running() -> bool:
    with _interruption_lock:
        return _interruption_stop_fn is not None


def _get_interruption_thread():
    for t in threading.enumerate():
        if "listen_in_background" in t.name or "threaded_listen" in t.name.lower() or "Threaded" in t.name:
            return t
    return None


def start_interruption_listener():
    global _interruption_stop_fn
    with _interruption_lock:
        if _interruption_stop_fn is not None:
            return
            
        logger.info("[VoiceInterrupt] Listener started | [ConfirmationMic] interruption_listener_running: True")
        try:
            m = sr.Microphone()
            _interruption_stop_fn = recognizer.listen_in_background(m, _interruption_callback, phrase_time_limit=3)
        except Exception as e:
            logger.error(f"[VoiceInterrupt] Failed to start listener: {e}")


def stop_interruption_listener():
    global _interruption_stop_fn
    with _interruption_lock:
        if _interruption_stop_fn is not None:
            logger.info("[ConfirmationMic] interruption_stop_requested")
            worker_t = _get_interruption_thread()
            alive_before = worker_t.is_alive() if worker_t else False
            logger.info(f"[ConfirmationMic] interruption_thread_alive_before_join: {alive_before}")
            try:
                _interruption_stop_fn(wait_for_stop=True)
            except Exception as exc:
                logger.debug(f"[ConfirmationMic] Stop notice: {exc}")
            _interruption_stop_fn = None
            alive_after = worker_t.is_alive() if worker_t else False
            logger.info(f"[ConfirmationMic] interruption_thread_alive_after_join: {alive_after}")
            logger.info("[ConfirmationMic] microphone_stream_released")


def listen(silent=False):
    from voice.speech_output import speaking

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

        global _active_mic_count
        with _mic_count_lock:
            _active_mic_count += 1
            logger.info(f"[ConfirmationMic] active_microphone_streams: {_active_mic_count}")

        try:
            m = sr.Microphone()
            with m as source:
                calibrate_ambient_noise(source, duration=0.5)
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                except sr.WaitTimeoutError:
                    if not silent:
                        logger.debug("[SpeechInput] Listen timeout: No speech detected within timeout window (5s)")
                    return ""
        finally:
            with _mic_count_lock:
                _active_mic_count -= 1
                logger.info(f"[ConfirmationMic] active_microphone_streams: {_active_mic_count}")

        t_stt_start = time.perf_counter()
        text = transcribe_audio(audio)
        stt_latency_ms = (time.perf_counter() - t_stt_start) * 1000.0
        total_listen_latency_ms = (time.perf_counter() - t_listen_start) * 1000.0
        logger.info(
            f"[Instrumentation] stt_latency_ms: {stt_latency_ms:.2f} ms | "
            f"total_listen_latency_ms: {total_listen_latency_ms:.2f} ms | "
            f"energy_threshold: {recognizer.energy_threshold:.2f}"
        )
        
        text_lower = text.lower().strip()
        now = time.time()
        global _last_transcript, _last_transcript_time
        if text_lower == _last_transcript and (now - _last_transcript_time) < 0.1:
            logger.info(f"[SpeechInput] Ignored rapid duplicate transcript: '{text_lower}'")
            return ""

        _last_transcript = text_lower
        _last_transcript_time = now
            
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


def listen_confirmation(expires_at: float) -> str:
    """
    Dedicated fast confirmation listener bound strictly to the single un-extended
    expires_at deadline of the active confirmation token.
    Fast iteration, tight timeout bounds, and dedicated instrumentation.
    """
    from voice.speech_output import speaking
    stop_interruption_listener()

    logger.info(
        f"[ConfirmationMic] confirmation_listener_start | "
        f"interruption_listener_running: {is_interruption_listener_running()} | "
        f"speaking: {speaking()}"
    )

    if speaking():
        time.sleep(0.1)

    while True:
        now = time.time()
        remaining = expires_at - now
        logger.info(f"[ConfirmationTiming] remaining_confirmation_ms: {remaining * 1000.0:.2f} ms")
        if remaining <= 0.2:
            logger.info("[ConfirmationMode] Confirmation window expired before speech capture.")
            return ""

        t_listen_start = time.perf_counter()
        listen_timeout = min(2.5, max(0.5, remaining))
        phrase_limit = min(4.0, max(0.5, remaining))

        try:
            global _active_mic_count
            with _mic_count_lock:
                _active_mic_count += 1
                logger.info(f"[ConfirmationMic] confirmation_microphone_opened | [ConfirmationMic] active_microphone_streams: {_active_mic_count}")

            try:
                m = sr.Microphone()
                with m as source:
                    calibrate_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(source, timeout=listen_timeout, phrase_time_limit=phrase_limit)
            finally:
                with _mic_count_lock:
                    _active_mic_count -= 1
                    logger.info(f"[ConfirmationMic] confirmation_microphone_closed | [ConfirmationMic] active_microphone_streams: {_active_mic_count}")

            t_stt_start = time.perf_counter()
            text = transcribe_audio(audio)
            t_stt_end = time.perf_counter()

            stt_latency_ms = (t_stt_end - t_stt_start) * 1000.0
            listen_latency_ms = (t_stt_start - t_listen_start) * 1000.0
            total_latency_ms = (t_stt_end - t_listen_start) * 1000.0

            logger.info(
                f"[ConfirmationInstrumentation] confirmation_stt_latency_ms: {stt_latency_ms:.2f} ms | "
                f"confirmation_listen_latency_ms: {listen_latency_ms:.2f} ms | "
                f"confirmation_total_latency_ms: {total_latency_ms:.2f} ms"
            )

            text_lower = text.lower().strip()
            if text_lower:
                logger.info(f"[ConfirmationMode] Speech captured: '{text_lower}'")
                return text_lower

        except sr.WaitTimeoutError:
            logger.debug("[ConfirmationMode] Short listen window timeout, retrying while valid...")
        except sr.UnknownValueError:
            logger.debug("[ConfirmationMode] Speech unrecognised in window, retrying while valid...")
        except sr.RequestError as e:
            logger.warning(f"[ConfirmationMode] Speech service request error: {e}")
            return ""
        except Exception as e:
            logger.error(f"[ConfirmationMode] Error: {e}")
            return ""


if __name__ == "__main__":
    while True:
        command = listen()
        if command:
            logger.info(f"Command: {command}")