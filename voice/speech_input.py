"""
ULTRON V3
Speech Input System
Sounddevice Microphone Handler
"""

import numpy as np
import sounddevice as sd
import speech_recognition as sr
import scipy.io.wavfile as wav
import tempfile
import os
from core.logger import logger
from core.config import config

recognizer = sr.Recognizer()


def listen(silent=False):
    if not silent:
        logger.info("Listening Boss...")

    temp_path = None

    try:
        sample_rate = config.AUDIO_SAMPLE_RATE
        duration = config.AUDIO_RECORD_DURATION

        if not silent:
            logger.info("Speak Boss...")

        # Dynamic VAD stream recording with early exit on silence
        chunks = []
        chunk_size = 1024
        silence_threshold = 300
        speech_detected = False
        silence_chunks = 0
        max_silence_chunks = int((0.6 * sample_rate) / chunk_size)
        max_total_chunks = int((duration * sample_rate) / chunk_size)
        min_speech_chunks = int((0.5 * sample_rate) / chunk_size)

        try:
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=chunk_size) as stream:
                for _ in range(max_total_chunks):
                    data, _ = stream.read(chunk_size)
                    chunks.append(data)

                    rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
                    if rms > silence_threshold:
                        speech_detected = True
                        silence_chunks = 0
                    elif speech_detected:
                        silence_chunks += 1
                        if silence_chunks >= max_silence_chunks and len(chunks) >= min_speech_chunks:
                            logger.debug("[SpeechInput] Silence detected after speech. Early stopping recording.")
                            break

            if chunks:
                recording = np.concatenate(chunks, axis=0)
            else:
                recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
                sd.wait()
        except Exception as err:
            logger.warning(f"[SpeechInput] Dynamic VAD fallback to fixed rec: {err}")
            recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
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
            if not silent:
                logger.info(f"You said: {text}")
            return text.lower()

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