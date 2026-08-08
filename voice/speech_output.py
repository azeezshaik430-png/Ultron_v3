"""
ULTRON V3
Stable Voice Output System

Version: 4.2
"""

import pyttsx3
import re
import threading

_tts_engine = None
_tts_lock = threading.Lock()


def _get_engine():
    global _tts_engine
    if _tts_engine is None:
        try:
            _tts_engine = pyttsx3.init()
            _tts_engine.setProperty("rate", 160)
            _tts_engine.setProperty("volume", 1.0)
        except Exception as e:
            print("TTS Engine Init Error:", e)
            _tts_engine = None
    return _tts_engine


# ==============================
# CLEAN TEXT
# ==============================

def clean_voice_text(text):
    text = str(text)
    text = re.sub(r"[*#_`]", "", text)
    text = text.replace("-", "")
    text = " ".join(text.split())
    return text


# ==============================
# SPEAK
# ==============================

def speak(text):
    if not text:
        return
    text = clean_voice_text(text)
    if not text:
        return

    with _tts_lock:
        try:
            engine = _get_engine()
            if engine:
                engine.say(text)
                engine.runAndWait()
        except Exception as e:
            print("Voice Error:", e)
            global _tts_engine
            _tts_engine = None


# ==============================
# STATUS
# ==============================

def speaking():
    return False


# ==============================
# STOP
# ==============================

def stop_speaking():
    with _tts_lock:
        global _tts_engine
        if _tts_engine:
            try:
                _tts_engine.stop()
            except Exception:
                pass