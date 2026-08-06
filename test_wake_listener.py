from voice.wake_listener import wait_for_wake_word
from voice.speech_output import speak


print("Testing Wake Listener")


wait_for_wake_word()


speak("Welcome back Boss. Ultron is active.")