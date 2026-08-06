"""
ULTRON V3
Speech Input System

Sounddevice Microphone Handler
No PyAudio Required

Version: 3.0
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

def listen():

    print("Listening Boss... 🎤")


    try:

        sample_rate = 16000
        duration = 5


        print("Speak Boss...")


        # Record microphone audio

        recording = sd.rec(

            int(duration * sample_rate),

            samplerate=sample_rate,

            channels=1,

            dtype="int16"

        )


        sd.wait()



        # Create temporary wav file

        temp_path = tempfile.mktemp(
            suffix=".wav"
        )


        wav.write(

            temp_path,

            sample_rate,

            recording

        )



        # Read audio

        with sr.AudioFile(temp_path) as source:

            audio = recognizer.record(source)



        # Delete temporary file

        try:

            os.remove(temp_path)

        except:

            pass




        # Convert speech to text

        try:

            text = recognizer.recognize_google(

                audio,

                language="en-IN"

            )


            print(

                "You said:",

                text

            )


            return text.lower()



        except sr.UnknownValueError:


            print(

                "Didn't understand Boss"

            )


            return ""



        except sr.RequestError:


            print(

                "Speech service unavailable"

            )


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