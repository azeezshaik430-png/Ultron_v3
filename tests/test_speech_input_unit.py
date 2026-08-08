"""
ULTRON V3 - Speech Input System Unit Test Suite
Comprehensive unit tests for voice/speech_input.py.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
import speech_recognition as sr
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import voice.speech_input as speech_input
from voice.speech_input import listen, calibrate_ambient_noise


def create_mock_microphone():
    mock_source = MagicMock(spec=sr.AudioSource)
    mock_source.stream = MagicMock()
    mock_source.stream.read.return_value = b"\x00" * 2048
    mock_source.CHUNK = 1024
    mock_source.SAMPLE_RATE = 16000
    mock_source.SAMPLE_WIDTH = 2
    mock_mic_instance = MagicMock()
    mock_mic_instance.__enter__.return_value = mock_source
    mock_mic_instance.__exit__.return_value = None
    return mock_mic_instance, mock_source


def create_mock_audio_data():
    return sr.AudioData(b"\x00" * 100, 16000, 2)


class TestSpeechInputUnit(unittest.TestCase):
    """Unit tests for speech_input module."""

    def setUp(self):
        # Reset calibration flag for clean testing state
        speech_input._calibrated = False

    @patch("speech_recognition.Recognizer.recognize_google")
    @patch("speech_recognition.Recognizer.listen")
    @patch("speech_recognition.Microphone")
    @patch("voice.speech_output.speaking", return_value=False)
    def test_01_normal_speech_recognition(self, mock_speaking, mock_mic, mock_listen, mock_recognize):
        """Test 1: Verify normal speech recognition returns lowercase transcript."""
        mock_mic_instance, mock_source = create_mock_microphone()
        mock_mic.return_value = mock_mic_instance

        mock_audio = create_mock_audio_data()
        mock_listen.return_value = mock_audio
        mock_recognize.return_value = "Hello Ultron"

        cmd = listen(silent=True)

        self.assertEqual(cmd, "hello ultron")
        mock_recognize.assert_called_once_with(mock_audio, language="en-IN")

    @patch("speech_recognition.Recognizer.listen", side_effect=sr.WaitTimeoutError)
    @patch("speech_recognition.Microphone")
    @patch("voice.speech_output.speaking", return_value=False)
    def test_02_silence_timeout_handling(self, mock_speaking, mock_mic, mock_listen):
        """Test 2: Verify WaitTimeoutError returns empty string cleanly without exception."""
        mock_mic_instance, _ = create_mock_microphone()
        mock_mic.return_value = mock_mic_instance

        cmd = listen(silent=True)
        self.assertEqual(cmd, "")

    @patch("speech_recognition.Recognizer.recognize_google", side_effect=sr.UnknownValueError)
    @patch("speech_recognition.Recognizer.listen")
    @patch("speech_recognition.Microphone")
    @patch("voice.speech_output.speaking", return_value=False)
    def test_03_unknown_speech_handling(self, mock_speaking, mock_mic, mock_listen, mock_recognize):
        """Test 3: Verify UnknownValueError returns empty string cleanly."""
        mock_mic_instance, _ = create_mock_microphone()
        mock_mic.return_value = mock_mic_instance
        mock_listen.return_value = create_mock_audio_data()

        cmd = listen(silent=True)
        self.assertEqual(cmd, "")

    @patch("speech_recognition.Recognizer.recognize_google", side_effect=sr.RequestError("Network error"))
    @patch("speech_recognition.Recognizer.listen")
    @patch("speech_recognition.Microphone")
    @patch("voice.speech_output.speaking", return_value=False)
    def test_04_stt_request_error_handling(self, mock_speaking, mock_mic, mock_listen, mock_recognize):
        """Test 4: Verify RequestError returns empty string cleanly."""
        mock_mic_instance, _ = create_mock_microphone()
        mock_mic.return_value = mock_mic_instance
        mock_listen.return_value = create_mock_audio_data()

        cmd = listen(silent=True)
        self.assertEqual(cmd, "")

    @patch("speech_recognition.Recognizer.adjust_for_ambient_noise")
    def test_05_cached_ambient_noise_calibration(self, mock_adjust):
        """Test 5: Verify lazy ambient noise calibration occurs once and is cached."""
        mock_source = MagicMock(spec=sr.AudioSource)

        self.assertFalse(speech_input._calibrated)

        calibrate_ambient_noise(mock_source, duration=0.5)
        self.assertTrue(speech_input._calibrated)
        self.assertEqual(mock_adjust.call_count, 1)

        # Second call should use cached calibration without calling adjust_for_ambient_noise again
        calibrate_ambient_noise(mock_source, duration=0.5)
        self.assertEqual(mock_adjust.call_count, 1)

    @patch("speech_recognition.Recognizer.recognize_google", return_value="Test Command")
    @patch("speech_recognition.Recognizer.listen")
    @patch("speech_recognition.Microphone")
    @patch("voice.speech_output.speaking", return_value=False)
    def test_06_repeated_listen_performance(self, mock_speaking, mock_mic, mock_listen, mock_recognize):
        """Test 6: Verify repeated listen calls process cleanly."""
        mock_mic_instance, _ = create_mock_microphone()
        mock_mic.return_value = mock_mic_instance
        mock_listen.return_value = create_mock_audio_data()

        c1 = listen(silent=True)
        c2 = listen(silent=True)

        self.assertEqual(c1, "test command")
        self.assertEqual(c2, "test command")
        self.assertEqual(mock_recognize.call_count, 2)

    @patch("voice.speech_input.listen", return_value="hey ultron")
    def test_07_wake_listener_integration(self, mock_listen):
        """Test 7: Verify wake word detection matches output from listen()."""
        from voice.wake_word import check_wake_word

        cmd = mock_listen(silent=True)
        wake = check_wake_word(cmd)

        self.assertTrue(wake)

    @patch("speech_recognition.Recognizer.recognize_google")
    @patch("speech_recognition.Recognizer.listen")
    @patch("speech_recognition.Microphone")
    @patch("voice.speech_output.speaking", return_value=False)
    def test_08_english_stt_language_routing(self, mock_speaking, mock_mic, mock_listen, mock_recognize):
        """Test 8: Verify English STT uses 'en-IN' language setting."""
        mock_mic_instance, _ = create_mock_microphone()
        mock_mic.return_value = mock_mic_instance
        mock_audio = create_mock_audio_data()
        mock_listen.return_value = mock_audio
        mock_recognize.return_value = "What time is it"

        cmd = listen(silent=True)

        self.assertEqual(cmd, "what time is it")
        mock_recognize.assert_called_with(mock_audio, language="en-IN")

    def test_09_recognizer_parameters(self):
        """Test 9: Verify recognizer dynamic threshold and pause parameters."""
        self.assertTrue(speech_input.recognizer.dynamic_energy_threshold)
        self.assertEqual(speech_input.recognizer.dynamic_energy_adjustment_damping, 0.15)
        self.assertEqual(speech_input.recognizer.dynamic_energy_ratio, 1.5)
        self.assertEqual(speech_input.recognizer.pause_threshold, 0.8)

    @patch("speech_recognition.Microphone", side_effect=OSError("No input device found"))
    @patch("voice.speech_output.speaking", return_value=False)
    def test_10_microphone_unavailable_error(self, mock_speaking, mock_mic):
        """Test 10: Verify microphone initialization failure handles exception cleanly."""
        cmd = listen(silent=True)
        self.assertEqual(cmd, "")


if __name__ == "__main__":
    unittest.main()
