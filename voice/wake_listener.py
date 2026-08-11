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


from typing import Tuple
from voice.wake_word import extract_wake_word_and_command
from core.config import config


def wait_for_wake_word() -> Tuple[bool, str]:
    logger.info("ULTRON sleeping... Waiting for wake word...")

    while True:
        try:
            command = listen(silent=True)
            if not command:
                continue

            command_str = command.lower().strip()
            has_wake, initial_cmd = extract_wake_word_and_command(command_str)
            if has_wake:
                t_wake_detected = time.perf_counter()
                logger.info(f"Wake word detected (Initial command: '{initial_cmd}')")

                from voice.speech_output import speak

                if session.is_authenticated or not getattr(config, "VOICE_AUTH_ENABLED", True):
                    if not getattr(config, "VOICE_AUTH_ENABLED", True):
                        logger.warning("==================================================")
                        logger.warning("⚠️ [DEV MODE] Voice authentication BYPASSED (VOICE_AUTH_ENABLED=false)")
                        logger.warning("==================================================")
                    session.set_auth(True)
                    if not initial_cmd:
                        speak("What can I do for you, Boss?")
                    return True, initial_cmd

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
                    if not initial_cmd:
                        speak("What can I do for you, Boss?")
                    return True, initial_cmd
                else:
                    logger.warning("Unknown voice detected. Access Denied. Returning to sleep...")
                    continue
        except Exception as e:
            logger.error(f"Wake Listener Error: {e}")