"""
ULTRON V3
Stable Voice Output System

Version: 4.1
"""

import threading
import pyttsx3
import re
from core.logger import logger

# Thread-Safe Voice State Control
_speaking_flag = threading.Event()
_stop_flag = threading.Event()
_engine_lock = threading.RLock()
_current_engine = None


def clean_voice_text(text: str) -> str:
    text = str(text)
    text = re.sub(r"[*#_`]", "", text)
    text = text.replace("-", " ")
    text = " ".join(text.split())
    return text


def speak(text: str) -> bool:
    """
    Synthesize and speak text chunk-by-chunk with interrupt support.
    Returns True if completed naturally, False if interrupted/stopped.
    """
    global _current_engine
    if not text:
        return True

    text = clean_voice_text(text)
    if not text:
        return True

    _stop_flag.clear()
    _speaking_flag.set()

    # Split text into sentence chunks for responsive sub-second interruption
    sentences = [s.strip() for s in re.split(r'(?<=[.!?]) +|\n+', text) if s.strip()]
    if not sentences:
        sentences = [text]

    interrupted = False

    try:
        for sentence in sentences:
            if _stop_flag.is_set():
                interrupted = True
                break

            with _engine_lock:
                if _stop_flag.is_set():
                    interrupted = True
                    break
                try:
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 160)
                    engine.setProperty("volume", 1.0)
                    _current_engine = engine
                except Exception as err:
                    logger.error(f"[VoiceOutput] Pyttsx3 init error: {err}")
                    _current_engine = None
                    continue

            try:
                engine.say(sentence)
                engine.runAndWait()
            except Exception as err:
                logger.debug(f"[VoiceOutput] RunAndWait notice: {err}")
            finally:
                with _engine_lock:
                    if _current_engine:
                        try:
                            _current_engine.stop()
                        except Exception:
                            pass
                        _current_engine = None

            if _stop_flag.is_set():
                interrupted = True
                break

    except Exception as e:
        logger.error(f"[VoiceOutput] Speech synthesis error: {e}")
    finally:
        _speaking_flag.clear()

    return not interrupted


def speaking() -> bool:
    """Return True if TTS engine is currently outputting speech."""
    return _speaking_flag.is_set()


def stop_speaking() -> None:
    """Immediately interrupt and stop ongoing TTS audio output."""
    global _current_engine
    logger.info("[VoiceOutput] Interruption triggered: Stopping TTS playback...")
    _stop_flag.set()
    _speaking_flag.clear()

    with _engine_lock:
        if _current_engine:
            try:
                _current_engine.stop()
            except Exception as e:
                logger.debug(f"[VoiceOutput] Engine stop notice: {e}")
            _current_engine = None