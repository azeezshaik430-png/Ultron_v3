"""
ULTRON V3
Wake Listener + Boss Voice Authentication
Voice Verification occurs ONLY ONCE per application run.
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
    os.makedirs("voice/samples", exist_ok=True)
    logger.info("Boss, please verify your voice... Recording starts in 2 seconds...")
    time.sleep(2)
    logger.info("Recording auth voice (5 seconds)...")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )
    sd.wait()
    write(AUTH_FILE, SAMPLE_RATE, audio)
    logger.info(f"Saved auth voice sample to: {AUTH_FILE}")
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
                logger.info("Wake word detected")

                # REQUIREMENT 1: Check session.is_authenticated BEFORE any audio recording or verification
                if session.is_authenticated:
                    logger.info("Session already authenticated. Immediately entering Active Mode.")
                    return True

                # INITIAL VOICE AUTHENTICATION (Runs ONLY ONCE per app launch)
                from voice.voice_guard import verify_boss
                voice_file = record_auth_voice()

                if verify_boss(voice_file):
                    session.set_auth(True)
                    logger.info("Boss Verified. Access Granted.")
                    return True
                else:
                    logger.warning("Unknown voice detected. Access Denied. Returning to sleep...")
                    continue
        except Exception as e:
            logger.error(f"Wake Listener Error: {e}")