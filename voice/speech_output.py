"""
ULTRON V3
Multi-Language Voice Output System with Sub-Second Interruption Support
Supports:
- English (en): Microsoft David Desktop (SAPI5 MALE Voice)
- Telugu (te): Piper ONNX te_IN-venkatesh-medium (Local Offline TELUGU MALE Voice)
"""

import os
import sys
import threading
import pyttsx3
import re
import sounddevice as sd
from core.config import config
from core.logger import logger
from core.session import session

# Thread-Safe Voice State Control
_speaking_flag = threading.Event()
_stop_flag = threading.Event()
_engine_lock = threading.RLock()
_current_engine = None
_piper_telugu_voice = None
_sapi5_engine = None
import time

def _get_sapi5_engine():
    global _sapi5_engine
    with _engine_lock:
        if _sapi5_engine is None:
            _init_com_if_needed()
            try:
                logger.info("[VoiceOutput] Initializing pyttsx3 SAPI5 engine...")
                _sapi5_engine = pyttsx3.init()
                rate = getattr(config, "VOICE_RATE", 170)
                volume = getattr(config, "VOICE_VOLUME", 1.0)
                _sapi5_engine.setProperty("rate", rate)
                _sapi5_engine.setProperty("volume", volume)
            except Exception as err:
                logger.error(f"[VoiceOutput] TTS_ERROR initializing SAPI5 engine: {err}")
                _sapi5_engine = None
    return _sapi5_engine


def clean_voice_text(text: str) -> str:
    text = str(text)
    text = re.sub(r"[*#_`]", "", text)
    text = text.replace("-", " ")
    text = " ".join(text.split())
    return text


def _init_com_if_needed() -> None:
    if sys.platform == "win32":
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass


def _get_piper_telugu_voice():
    """Lazy load local Piper ONNX Telugu Male Voice (te_IN-venkatesh-medium)."""
    global _piper_telugu_voice
    if _piper_telugu_voice is not None:
        return _piper_telugu_voice

    with _engine_lock:
        if _piper_telugu_voice is not None:
            return _piper_telugu_voice

        model_dir = os.path.join("voice", "models", "telugu")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, "te_IN-venkatesh-medium.onnx")
        json_path = os.path.join(model_dir, "te_IN-venkatesh-medium.onnx.json")

        if not os.path.exists(model_path) or not os.path.exists(json_path):
            logger.info("[VoiceOutput] Downloading local Piper Telugu MALE model (te_IN-venkatesh-medium)...")
            try:
                import urllib.request
                onnx_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/venkatesh/medium/te_IN-venkatesh-medium.onnx"
                json_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/venkatesh/medium/te_IN-venkatesh-medium.onnx.json"
                req1 = urllib.request.Request(onnx_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req1) as resp, open(model_path, "wb") as f:
                    f.write(resp.read())
                req2 = urllib.request.Request(json_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2) as resp, open(json_path, "wb") as f:
                    f.write(resp.read())
                logger.info("[VoiceOutput] Piper Telugu model downloaded successfully.")
            except Exception as d_err:
                logger.error(f"[VoiceOutput] Failed to download Piper Telugu model: {d_err}")
                return None

        try:
            from piper import PiperVoice
            logger.info(f"[VoiceOutput] Loading local Piper Telugu MALE model: {model_path}")
            voice = PiperVoice.load(model_path, config_path=json_path)
            _piper_telugu_voice = voice
            logger.info("[VoiceOutput] TTS_TELUGU_VOICE_LOADED: 'te_IN-venkatesh-medium' (TELUGU MALE)")
            return _piper_telugu_voice
        except Exception as err:
            logger.error(f"[VoiceOutput] Failed to load Piper Telugu voice: {err}")
            return None


def is_telugu_text(text: str) -> bool:
    """Detect if text contains Telugu Unicode characters (U+0C00 to U+0C7F)."""
    return any(ord('\u0c00') <= ord(char) <= ord('\u0c7f') for char in text)


def speak(text: str, language: str = None) -> bool:
    """
    Synthesize and speak text with sub-second interrupt support and real audio output.
    Routes to Microsoft David (English MALE) or Piper te_IN-venkatesh-medium (Telugu MALE).
    Returns True if completed naturally, False if interrupted/stopped.
    """
    global _current_engine
    if not text:
        return True

    clean_txt = clean_voice_text(text)
    if not clean_txt:
        return True

    if language is None:
        language = getattr(session, "preferred_language", "en")
        if is_telugu_text(clean_txt):
            language = "te"

    logger.info(f"[VoiceOutput] TTS_REQUESTED (Lang: '{language}'): '{clean_txt[:60]}...'")

    _stop_flag.clear()
    _speaking_flag.set()

    from voice.speech_input import start_interruption_listener, stop_interruption_listener
    start_interruption_listener()

    try:
        if language == "te":
            engine_test = _get_sapi5_engine()
            voices = engine_test.getProperty("voices") if engine_test else []
            sapi_telugu_voice = None
            for v in voices:
                if "telugu" in v.name.lower() or "te-" in v.id.lower():
                    sapi_telugu_voice = v
                    break

            if sapi_telugu_voice:
                return _speak_sapi5_with_voice(clean_txt, sapi_telugu_voice, "te")
            else:
                return _speak_telugu_piper(clean_txt)
        else:
            return _speak_english_sapi5(clean_txt)
    finally:
        stop_interruption_listener()

def _speak_sapi5_with_voice(clean_txt: str, voice, lang: str) -> bool:
    """Synthesize text using a specific Windows SAPI5 voice."""
    global _current_engine, _sapi5_engine
    engine = _get_sapi5_engine()
    if engine is None:
        return False

    t_start = time.perf_counter()
    with _engine_lock:
        try:
            engine.setProperty("voice", voice.id)
            logger.info(
                f"[VoiceOutput] TTS_SELECTED_VOICE: '{voice.name}' | "
                f"Gender: Unknown | ID: '{voice.id}'"
            )
            _current_engine = engine
        except Exception as err:
            logger.error(f"[VoiceOutput] TTS_ERROR configuring voice on SAPI5 engine: {err}")
            _speaking_flag.clear()
            _current_engine = None
            return False

    interrupted = False
    logger.info("[VoiceOutput] TTS_PLAYBACK_STARTED")

    try:
        if not _stop_flag.is_set():
            engine.say(clean_txt)
            tts_latency_ms = (time.perf_counter() - t_start) * 1000.0
            logger.info(f"[Instrumentation] tts_latency_ms: {tts_latency_ms:.2f} ms")
            engine.runAndWait()

        if _stop_flag.is_set():
            interrupted = True
            logger.info("[VoiceOutput] TTS_INTERRUPTED during speech playback")
        else:
            logger.info("[VoiceOutput] TTS_PLAYBACK_FINISHED")

    except Exception as e:
        logger.error(f"[VoiceOutput] TTS_ERROR during speech playback: {e}")
        interrupted = True
    finally:
        with _engine_lock:
            _current_engine = None
            if _sapi5_engine is not None:
                try:
                    _sapi5_engine.stop()
                except Exception:
                    pass
                _sapi5_engine = None
        _speaking_flag.clear()

    return not interrupted

def _speak_telugu_piper(clean_txt: str) -> bool:
    """Synthesize Telugu text using local Piper ONNX male voice engine."""
    t_start = time.perf_counter()
    voice = _get_piper_telugu_voice()
    if voice is None:
        logger.warning("[VoiceOutput] Piper Telugu voice unavailable. Falling back to SAPI5 English.")
        return _speak_english_sapi5(clean_txt)
 
    logger.info("[VoiceOutput] TTS_ENGINE_READY (Voice: 'te_IN-venkatesh-medium' | Gender: Male | Lang: te)")
    tts_latency_ms = (time.perf_counter() - t_start) * 1000.0
    logger.info(f"[Instrumentation] tts_latency_ms: {tts_latency_ms:.2f} ms")
    logger.info("[VoiceOutput] TTS_PLAYBACK_STARTED")

    interrupted = False
    try:
        for chunk in voice.synthesize(clean_txt):
            if _stop_flag.is_set():
                interrupted = True
                logger.info("[VoiceOutput] TTS_INTERRUPTED during Telugu speech playback")
                break

            sd.play(chunk.audio_int16_array, samplerate=chunk.sample_rate)

            duration_sec = len(chunk.audio_int16_array) / float(chunk.sample_rate)
            steps = int(duration_sec * 50)
            for _ in range(max(1, steps)):
                if _stop_flag.is_set():
                    interrupted = True
                    sd.stop()
                    logger.info("[VoiceOutput] TTS_INTERRUPTED during active audio output")
                    break
                sd.sleep(20)

            if interrupted:
                break

        if not interrupted:
            logger.info("[VoiceOutput] TTS_PLAYBACK_FINISHED")

    except Exception as err:
        logger.error(f"[VoiceOutput] TTS_ERROR during Piper Telugu speech playback: {err}")
        interrupted = True
    finally:
        _speaking_flag.clear()

    return not interrupted


def _speak_english_sapi5(clean_txt: str) -> bool:
    """Synthesize English text using Windows SAPI5 Microsoft David (Male) engine."""
    global _current_engine, _sapi5_engine
    engine = _get_sapi5_engine()
    if engine is None:
        return False

    t_start = time.perf_counter()
    with _engine_lock:
        try:
            voices = engine.getProperty("voices")
            selected_voice = None
            male_keywords = ["david", "male", "mark", "george", "james", "richard", "guy"]
            if voices:
                for v in voices:
                    name_lower = v.name.lower()
                    if any(k in name_lower for k in male_keywords):
                        selected_voice = v
                        break
                if not selected_voice:
                    selected_voice = voices[0]

                engine.setProperty("voice", selected_voice.id)
                logger.info(
                    f"[VoiceOutput] TTS_SELECTED_VOICE: '{selected_voice.name}' | "
                    f"Gender: Male | ID: '{selected_voice.id}'"
                )
            _current_engine = engine
        except Exception as err:
            logger.error(f"[VoiceOutput] TTS_ERROR configuring voice on SAPI5 engine: {err}")
            _speaking_flag.clear()
            _current_engine = None
            return False

    interrupted = False
    logger.info("[VoiceOutput] TTS_PLAYBACK_STARTED")

    try:
        if not _stop_flag.is_set():
            engine.say(clean_txt)
            tts_latency_ms = (time.perf_counter() - t_start) * 1000.0
            logger.info(f"[Instrumentation] tts_latency_ms: {tts_latency_ms:.2f} ms")
            engine.runAndWait()

        if _stop_flag.is_set():
            interrupted = True
            logger.info("[VoiceOutput] TTS_INTERRUPTED during speech playback")
        else:
            logger.info("[VoiceOutput] TTS_PLAYBACK_FINISHED")

    except Exception as e:
        logger.error(f"[VoiceOutput] TTS_ERROR during speech playback: {e}")
        interrupted = True
    finally:
        with _engine_lock:
            _current_engine = None
            if _sapi5_engine is not None:
                try:
                    _sapi5_engine.stop()
                except Exception:
                    pass
                _sapi5_engine = None
        _speaking_flag.clear()

    return not interrupted


def speaking() -> bool:
    """Return True if TTS engine is currently outputting speech."""
    return _speaking_flag.is_set()


def stop_speaking() -> None:
    """Immediately interrupt and stop ongoing TTS audio output (English & Telugu)."""
    global _current_engine, _sapi5_engine
    logger.info("[VoiceOutput] Interruption triggered: Stopping TTS playback...")
    _stop_flag.set()
    _speaking_flag.clear()

    try:
        sd.stop()
    except Exception:
        pass

    with _engine_lock:
        if _current_engine:
            try:
                _current_engine.stop()
            except Exception as e:
                logger.debug(f"[VoiceOutput] Engine stop notice: {e}")
            _current_engine = None
        if _sapi5_engine:
            try:
                _sapi5_engine.stop()
            except Exception:
                pass
            _sapi5_engine = None