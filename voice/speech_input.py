"""
ULTRON V3
Speech Input System
Sounddevice Microphone Handler
"""

import sounddevice as sd
import speech_recognition as sr
import scipy.io.wavfile as wav
import tempfile
import os
from core.logger import logger
from core.config import config

recognizer = sr.Recognizer()


import threading

_interruption_stop_fn = None
_interruption_lock = threading.Lock()

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
                _interruption_stop_fn(wait_for_stop=False)
            except Exception:
                pass
            _interruption_stop_fn = None

def listen(silent=False):
    from voice.speech_output import speaking, stop_speaking
    
    # Do not record while speaking if we are handling it in background
    if speaking():
        import time
        time.sleep(0.5)
        return ""

    if not silent:
        logger.info("Listening Boss...")

    temp_path = None

    try:
        sample_rate = config.AUDIO_SAMPLE_RATE
        duration = config.AUDIO_RECORD_DURATION

        if not silent:
            logger.info("Speak Boss...")

        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16"
        )
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name

        wav.write(temp_path, sample_rate, recording)

        with sr.AudioFile(temp_path) as source:
            audio = recognizer.record(source)

        try:
            text = recognizer.recognize_google(
                audio,
                language="en-IN"
            )
            text_lower = text.lower()
                
            if not silent:
                logger.info(f"You said: {text}")
            return text_lower

        except sr.UnknownValueError:
            if not silent:
                logger.info("Didn't understand Boss")
            return ""

        except sr.RequestError:
            if not silent:
                logger.warning("Speech service unavailable")
            return ""

    except KeyboardInterrupt:
        logger.info("Voice input stopped")
        return ""

    except Exception as e:
        logger.error(f"Voice Error: {e}")
        return ""

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


if __name__ == "__main__":
    while True:
        command = listen()
        if command:
            logger.info(f"Command: {command}")