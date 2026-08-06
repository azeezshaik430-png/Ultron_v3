"""
ULTRON V3
Stable Voice Output System

Version: 4.1
"""

import pyttsx3
import re


# ==============================
# CLEAN TEXT
# ==============================

def clean_voice_text(text):

    text = str(text)

    text = re.sub(
        r"[*#_`]",
        "",
        text
    )

    text = text.replace(
        "-",
        ""
    )

    text = " ".join(
        text.split()
    )

    return text



# ==============================
# SPEAK
# ==============================

def speak(text):

    try:

        text = clean_voice_text(text)


        engine = pyttsx3.init()


        engine.setProperty(
            "rate",
            160
        )


        engine.setProperty(
            "volume",
            1.0
        )


        engine.say(
            text
        )


        engine.runAndWait()


        engine.stop()



    except Exception as e:


        print(
            "Voice Error:",
            e
        )



# ==============================
# STATUS
# ==============================

def speaking():

    return False



# ==============================
# STOP
# ==============================

def stop_speaking():

    pass