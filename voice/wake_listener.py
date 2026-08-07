"""
ULTRON V3
Wake Listener + Boss Voice Authentication
Voice Verification occurs ONLY ONCE per application run.
Optimized for zero-wait recording and background preloaded VoiceEncoder.
"""

import os
import time
import sounddevice as sd
from scipy.io.wavfile import write
from voice.speech_input import listen
from voice.wake_word import check_wake_word
from core.logger import logger
from core.session import session

SAMPLE_RATE = 16000
DURATION = 5  # 5s verification sample
AUTH_FILE = "voice/samples/auth_test.wav"


def record_auth_voice() -> str:
    t_start = time.perf_counter()
    os.makedirs("voice/samples", exist_ok=True)
    logger.info("Boss, please verify your voice... Recording auth voice (5 seconds)...")
    # REMOVED: Unnecessary time.sleep(2) wait removed for instant response

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )
    sd.wait()
    write(AUTH_FILE, SAMPLE_RATE, audio)
    rec_ms = (time.perf_counter() - t_start) * 1000.0
    logger.info(f"[VoiceGuard Telemetry] Auth voice recorded ({rec_ms:.2f} ms) to: {AUTH_FILE}")
    return AUTH_FILE


def wait_for_wake_word() -> bool:
    logger.info("ULTRON sleeping... Waiting for wake word...")

    while True:
        try:
            command = listen(silent=True)
            if not command:
                continue

            command = command.lower().strip()
            if check_wake_word(command):
                t_wake_detected = time.perf_counter()
                logger.info("Wake word detected")

                # REQUIREMENT 1: Check session.is_authenticated BEFORE any audio recording or verification
                if session.is_authenticated:
                    logger.info("Session already authenticated. Immediately entering Active Mode.")
                    return True

                # INITIAL VOICE AUTHENTICATION (Runs ONLY ONCE per app launch)
                t_rec_start = time.perf_counter()
                from voice.voice_guard import verify_boss
                voice_file = record_auth_voice()

                t_verify_start = time.perf_counter()
                verified = verify_boss(voice_file)
                t_verify_end = time.perf_counter()

                wake_to_rec_ms = (t_rec_start - t_wake_detected) * 1000.0
                verify_duration_ms = (t_verify_end - t_verify_start) * 1000.0
                total_auth_ms = (t_verify_end - t_wake_detected) * 1000.0

                logger.info("==================================================")
                logger.info("🎤 [VOICE RESPONSE SPEED TELEMETRY]")
                logger.info(f"   Wake Detection -> Rec Start: {wake_to_rec_ms:.2f} ms")
                logger.info(f"   Verification Engine Time:   {verify_duration_ms:.2f} ms")
                logger.info(f"   TOTAL FIRST RESPONSE LATENCY: {total_auth_ms:.2f} ms")
                logger.info("==================================================")

                if verified:
                    session.set_auth(True)
                    logger.info("Boss Verified. Access Granted.")
                    return True
                else:
                    logger.warning("Unknown voice detected. Access Denied. Returning to sleep...")
                    continue
        except Exception as e:
            logger.error(f"Wake Listener Error: {e}")