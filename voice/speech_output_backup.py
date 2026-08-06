"""
ULTRON V3
Advanced Voice Output System
Thread Ready
"""

import pyttsx3
import threading


engine = pyttsx3.init()

engine.setProperty("rate", 160)
engine.setProperty("volume", 1.0)


is_speaking = False


def _speak(text):

    global is_speaking

    try:

        is_speaking = True

        engine.say(str(text))
        engine.runAndWait()

    except Exception as e:

        print("Voice Error:", e)

    finally:

        is_speaking = False


def speak(text):

    thread = threading.Thread(
        target=_speak,
        args=(text,),
        daemon=True
    )

    thread.start()


def stop_speaking():

    global is_speaking

    try:

        engine.stop()

    except:
        pass

    is_speaking = False


def speaking():

    return is_speaking