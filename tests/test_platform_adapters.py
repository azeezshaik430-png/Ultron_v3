"""
ULTRON V3 - Platform Adapters Unit Test Suite
Verifies cross-platform adapter contract, factory loading, capability status reporting,
and graceful fallback handling for Windows, Linux, and macOS.
"""

import sys
import unittest
from unittest.mock import patch

from ultron_platform import (
    get_platform_adapter,
    is_linux,
    is_macos,
    is_windows,
    platform_name,
)
from ultron_platform.interface import CapabilityStatus, PlatformAdapter
from ultron_platform.linux_adapter import LinuxAdapter
from ultron_platform.macos_adapter import MacOSAdapter
from ultron_platform.windows_adapter import WindowsAdapter


class TestPlatformAdapterFactory(unittest.TestCase):

    def test_windows_platform_detection(self):
        with patch("sys.platform", "win32"):
            self.assertEqual(platform_name(), "Windows")
            self.assertTrue(is_windows())
            self.assertFalse(is_linux())
            self.assertFalse(is_macos())

    def test_linux_platform_detection(self):
        with patch("sys.platform", "linux"):
            self.assertEqual(platform_name(), "Linux")
            self.assertTrue(is_linux())
            self.assertFalse(is_windows())
            self.assertFalse(is_macos())

    def test_macos_platform_detection(self):
        with patch("sys.platform", "darwin"):
            self.assertEqual(platform_name(), "macOS")
            self.assertTrue(is_macos())
            self.assertFalse(is_windows())
            self.assertFalse(is_linux())

    def test_factory_returns_windows_adapter_on_win32(self):
        with patch("sys.platform", "win32"), patch("ultron_platform._adapter_instance", None):
            adapter = get_platform_adapter()
            self.assertIsInstance(adapter, WindowsAdapter)
            self.assertEqual(adapter.platform_name, "Windows")

    def test_factory_returns_linux_adapter_on_linux(self):
        with patch("sys.platform", "linux"), patch("ultron_platform._adapter_instance", None):
            adapter = get_platform_adapter()
            self.assertIsInstance(adapter, LinuxAdapter)
            self.assertEqual(adapter.platform_name, "Linux")

    def test_factory_returns_macos_adapter_on_darwin(self):
        with patch("sys.platform", "darwin"), patch("ultron_platform._adapter_instance", None):
            adapter = get_platform_adapter()
            self.assertIsInstance(adapter, MacOSAdapter)
            self.assertEqual(adapter.platform_name, "macOS")


class TestPlatformCapabilityContract(unittest.TestCase):

    def test_windows_adapter_capabilities(self):
        adapter = WindowsAdapter()
        caps = adapter.get_capabilities()
        self.assertIsInstance(caps, dict)
        self.assertIn("open_application", caps)
        self.assertEqual(caps["open_application"], CapabilityStatus.SUPPORTED)
        self.assertEqual(adapter.get_capability_status("open_application"), CapabilityStatus.SUPPORTED)

    def test_linux_adapter_capabilities(self):
        adapter = LinuxAdapter()
        caps = adapter.get_capabilities()
        self.assertIsInstance(caps, dict)
        self.assertIn("open_application", caps)
        self.assertEqual(adapter.get_capability_status("open_application"), CapabilityStatus.SUPPORTED)

    def test_macos_adapter_capabilities(self):
        adapter = MacOSAdapter()
        caps = adapter.get_capabilities()
        self.assertIsInstance(caps, dict)
        self.assertIn("open_application", caps)
        self.assertEqual(adapter.get_capability_status("open_application"), CapabilityStatus.SUPPORTED)
        self.assertEqual(adapter.get_capability_status("mouse_click"), CapabilityStatus.REQUIRES_PERMISSION)

    def test_unsupported_capability_query_returns_unsupported(self):
        adapter = WindowsAdapter()
        self.assertEqual(adapter.get_capability_status("nonexistent_teleportation_cap"), CapabilityStatus.UNSUPPORTED)


class TestPlatformAdapterGracefulFallbacks(unittest.TestCase):

    def test_macos_adapter_graceful_fallback_on_non_darwin(self):
        adapter = MacOSAdapter()
        # Executing on Windows host -> returns structured fallback without crashing
        res = adapter.open_application("/Applications/Safari.app")
        self.assertIsInstance(res, dict)
        self.assertFalse(res["available"])
        self.assertEqual(res["status"], CapabilityStatus.NOT_AVAILABLE)

    def test_linux_adapter_graceful_fallback_on_missing_brightnessctl(self):
        adapter = LinuxAdapter()
        with patch("ultron_platform.linux_adapter._which", return_value=None):
            res = adapter.set_brightness(0.5)
            self.assertIsInstance(res, dict)
            self.assertFalse(res["available"])
            self.assertEqual(res["status"], CapabilityStatus.NOT_AVAILABLE)
            self.assertIn("brightnessctl", res["reason"])

    def test_windows_adapter_graceful_fallback_on_invalid_app(self):
        adapter = WindowsAdapter()
        res = adapter.open_application("C:\\nonexistent\\app.exe")
        self.assertIsInstance(res, dict)
        self.assertTrue(res["available"])
        self.assertIn("Path not found", res.get("error", ""))


if __name__ == "__main__":
    unittest.main()
