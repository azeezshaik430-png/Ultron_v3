"""
ULTRON V3
Speech Input System

Sounddevice Microphone Handler
No PyAudio Required

Version: 3.2
"""

import sounddevice as sd
import speech_recognition as sr
import scipy.io.wavfile as wav
import tempfile
import os


# ==============================
# INITIALIZE RECOGNIZER
# ==============================

recognizer = sr.Recognizer()



# ==============================
# VOICE LISTEN FUNCTION
# ==============================

def listen(silent=False):

    if not silent:
        print("Listening Boss... 🎤")


    temp_path = None


    try:

        sample_rate = 16000
        duration = 5


        if not silent:
            print("Speak Boss...")


        # Record audio from microphone

        recording = sd.rec(

            int(duration * sample_rate),

            samplerate=sample_rate,

            channels=1,

            dtype="int16"

        )


        sd.wait()



        # Create temporary wav file

        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as temp_file:

            temp_path = temp_file.name



        # Save recording

        wav.write(

            temp_path,

            sample_rate,

            recording

        )



        # Read audio

        with sr.AudioFile(temp_path) as source:

            audio = recognizer.record(source)



        # Convert speech to text

        try:

            text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )


            if not silent:

                print(
                    "You said:",
                    text
                )


            return text.lower()



        except sr.UnknownValueError:


            if not silent:
                print("Didn't understand Boss")


            return ""



        except sr.RequestError:


            if not silent:
                print("Speech service unavailable")


            return ""




    except KeyboardInterrupt:


        print(
            "Voice input stopped"
        )

        return ""




    except Exception as e:


        print(
            "Voice Error:",
            e
        )

        return ""




    finally:


        # Remove temporary file safely

        if temp_path and os.path.exists(temp_path):

            try:

                os.remove(temp_path)

            except:

                pass




# ==============================
# TEST MODE
# ==============================

if __name__ == "__main__":


    while True:


        command = listen()


        if command:


            print(

                "Command:",

                command

            )