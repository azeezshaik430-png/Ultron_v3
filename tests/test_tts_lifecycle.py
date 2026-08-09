import unittest
import time
import os
from voice.speech_output import speak, stop_speaking, speaking, clean_voice_text, is_telugu_text, _get_sapi5_engine
from brain.orchestrator import orchestrator
from core.config import config
from core.session import session


class TestTTSLifecycle(unittest.TestCase):

    def setUp(self):
        config.VOICE_AUTH_ENABLED = False
        session.reset()
        session.session_data.clear()
        session.preferred_language = "en"
        session.set_auth(True)
        session.enter_active()

    def test_01_first_tts(self):
        res = speak("Testing first utterance.")
        self.assertTrue(res, "First speak() should return True")

    def test_02_second_tts(self):
        res1 = speak("Testing first utterance.")
        self.assertTrue(res1)
        res2 = speak("Testing second utterance.")
        self.assertTrue(res2, "Second speak() should return True")

    def test_03_third_tts(self):
        res1 = speak("Testing utterance one.")
        res2 = speak("Testing utterance two.")
        res3 = speak("Testing third utterance.")
        self.assertTrue(res3, "Third speak() should return True")

    def test_04_stop_then_next_tts(self):
        speak("Testing speech before stop.")
        stop_speaking()
        self.assertFalse(speaking(), "speaking() should return False after stop_speaking()")
        res = speak("Testing speech after stop_speaking().")
        self.assertTrue(res, "speak() should complete after stop_speaking()")

    def test_05_interruption_then_next_tts(self):
        stop_speaking()
        res1 = speak("Testing recovery speech after interruption.")
        self.assertTrue(res1)
        stop_speaking()
        res2 = speak("Testing recovery speech after second interruption.")
        self.assertTrue(res2)

    def test_06_repeated_tts(self):
        for i in range(5):
            res = speak(f"Repeated TTS test number {i+1}")
            self.assertTrue(res, f"Iteration {i+1} should return True")

    def test_07_engine_lifecycle(self):
        # Verify engine initialization and cleanup lifecycle
        engine = _get_sapi5_engine()
        self.assertIsNotNone(engine, "SAPI5 engine should be initializable")
        voices = engine.getProperty("voices")
        self.assertGreater(len(voices), 0, "Engine should expose SAPI5 voices")

    def test_08_volume_command_response_tts(self):
        cmd_res = orchestrator.process_command("volume up")
        self.assertIn("Volume is now", cmd_res)
        speak_res = speak(cmd_res)
        self.assertTrue(speak_res, "TTS for volume command response should succeed")

    def test_09_browser_command_response_tts(self):
        cmd_res = orchestrator.process_command("open brave")
        self.assertIn("What website would you like me to open", cmd_res)
        speak_res = speak(cmd_res)
        self.assertTrue(speak_res, "TTS for browser command response should succeed")

    def test_10_telugu_tanglish_response_tts(self):
        telugu_txt = "నమస్కారం బాస్, ULTRON వ్యవస్థ సిద్ధంగా ఉంది."
        self.assertTrue(is_telugu_text(telugu_txt))
        speak_res = speak(telugu_txt, language="te")
        self.assertTrue(speak_res, "TTS for Telugu text should succeed")


if __name__ == "__main__":
    unittest.main()
