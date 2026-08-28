"""
ULTRON V3 - Computer-Use OCR Fallback Tests

Tests the _fallback_ocr() function and _observe() OCR behavior:
- OCR success with pytesseract
- OCR unavailable (ImportError)
- Empty/no-text screen
- OCR exception/failure
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from core.computer_use import _fallback_ocr, _observe


class TestFallbackOCR(unittest.TestCase):
    """Tests for the _fallback_ocr() helper function."""

    def _make_test_image(self, width=100, height=50, color=(255, 255, 255)):
        """Create a simple PIL test image."""
        return Image.new("RGB", (width, height), color)

    def test_ocr_success_extracts_text(self):
        """When pytesseract is available and image has text, extract it."""
        img = self._make_test_image()
        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.return_value = "Hello World"

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            result = _fallback_ocr(img)

        self.assertEqual(result, "Hello World")

    def test_ocr_success_with_whitespace_only(self):
        """When pytesseract returns only whitespace, return fallback message."""
        img = self._make_test_image()
        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.return_value = "   \n  \n  "

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            result = _fallback_ocr(img)

        self.assertIn("100x50", result)
        self.assertIn("no text", result)

    def test_ocr_unavailable_returns_graceful_message(self):
        """When pytesseract is not installed, return graceful fallback."""
        img = self._make_test_image()

        def import_side_effect(name, *args, **kwargs):
            if name == "pytesseract":
                raise ImportError("No module named 'pytesseract'")
            return __builtins__.__import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = _fallback_ocr(img)

        self.assertIn("OCR unavailable", result)
        self.assertIn("100x50", result)

    def test_ocr_empty_screen_returns_message(self):
        """When image has no text content, OCR returns empty and fallback triggers."""
        img = self._make_test_image()
        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.return_value = ""

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            result = _fallback_ocr(img)

        self.assertIn("no text", result)

    def test_ocr_exception_returns_graceful_message(self):
        """When pytesseract raises an exception, return graceful fallback."""
        img = self._make_test_image()
        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.side_effect = RuntimeError("tesseract not found")

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            result = _fallback_ocr(img)

        self.assertIn("OCR failed", result)
        self.assertIn("100x50", result)

    def test_ocr_preserves_image_dimensions_in_fallback(self):
        """Fallback messages should include image dimensions."""
        img = self._make_test_image(width=1920, height=1080)

        def import_side_effect(name, *args, **kwargs):
            if name == "pytesseract":
                raise ImportError("No module named 'pytesseract'")
            return __builtins__.__import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_side_effect):
            result = _fallback_ocr(img)

        self.assertIn("1920x1080", result)

    def test_ocr_with_mocked_tesseract_path_discovery(self):
        """Verify Tesseract path discovery is attempted."""
        img = self._make_test_image()
        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.return_value = "found"
        mock_pytesseract.pytesseract = MagicMock()
        mock_pytesseract.pytesseract.tesseract_cmd = "tesseract"

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            with patch("shutil.which", return_value=None):
                result = _fallback_ocr(img)

        self.assertEqual(result, "found")


class TestObserveOCR(unittest.TestCase):
    """Tests for the _observe() function OCR integration."""

    def test_observe_pil_fallback_runs_ocr(self):
        """_observe() without vision_agent should capture screenshot + run OCR."""
        mock_img = Image.new("RGB", (100, 50), (255, 255, 255))

        with patch("core.computer_use.os.path.exists", return_value=False):
            # Mock PIL ImageGrab
            mock_grab = MagicMock(return_value=mock_img)
            mock_imagegrab = MagicMock()
            mock_imagegrab.grab = mock_grab

            with patch.dict("sys.modules", {"PIL.ImageGrab": mock_imagegrab}):
                # Mock pytesseract
                mock_pytesseract = MagicMock()
                mock_pytesseract.image_to_string.return_value = "Test OCR Text"

                with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
                    # Ensure os.makedirs works
                    with patch("core.computer_use.os.makedirs"):
                        result = _observe(vision_agent=None)

        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("filepath", result)
        # Text should be actual OCR output, not just a filepath string
        self.assertIsInstance(result["text"], str)
        self.assertTrue(len(result["text"]) > 0)


if __name__ == "__main__":
    unittest.main()
