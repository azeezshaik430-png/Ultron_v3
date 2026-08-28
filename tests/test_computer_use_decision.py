"""
ULTRON V3 - Computer-Use Decision Layer Tests

Tests the enhanced decision architecture:
- Screen dimensions in prompt
- Coordinate bounds validation
- Invalid action protection
- Multi-step action plans
- Application launch patterns
- (0,0) rejection
- Safety preservation
"""

import unittest
from unittest.mock import patch, MagicMock

from core.computer_use import (
    _validate_action,
    _get_app_launch_plan,
    _decide,
    FORBIDDEN_ACTIONS,
    CONFIRMATION_REQUIRED,
    VALID_ACTION_TYPES,
    MAX_ITERATIONS,
    _KNOWN_APPS,
)


class TestScreenDimensions(unittest.TestCase):
    """Tests that screen dimensions are passed to the decision layer."""

    def test_observe_returns_dimensions(self):
        """_observe() should return width and height."""
        from core.computer_use import _observe
        from unittest.mock import patch, MagicMock
        from PIL import Image

        mock_img = Image.new("RGB", (800, 600), (128, 128, 128))

        # Mock ImageGrab.grab to return our small test image
        mock_imagegrab_module = MagicMock()
        mock_imagegrab_module.grab.return_value = mock_img

        with patch("core.computer_use.os.path.exists", return_value=False):
            with patch("core.computer_use.os.makedirs"):
                with patch("PIL.ImageGrab.grab", return_value=mock_img):
                    result = _observe(vision_agent=None)

        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("width", result)
        self.assertIn("height", result)
        self.assertEqual(result["width"], 800)
        self.assertEqual(result["height"], 600)

    def test_decide_includes_dimensions_in_prompt(self):
        """_decide() should include screen dimensions in the LLM prompt."""
        mock_llm = MagicMock()
        mock_llm.ask.return_value = '{"action_type": "wait", "details": "test"}'

        with patch("brain.llm_manager.llm_manager", mock_llm):
            _decide("test task", "screen text", 1920, 1080, 1)

        call_args = mock_llm.ask.call_args[0][0]
        self.assertIn("1920x1080", call_args)
        self.assertIn("0,0", call_args)


class TestCoordinateValidation(unittest.TestCase):
    """Tests for coordinate bounds checking."""

    def test_valid_click_passes(self):
        """Click at (500, 300) on 1920x1080 screen should pass."""
        result = _validate_action(
            {"action_type": "click", "x": 500, "y": 300, "details": "test"},
            1920, 1080,
        )
        self.assertTrue(result["valid"])

    def test_zero_zero_rejected(self):
        """Click at (0,0) should be rejected as likely default."""
        result = _validate_action(
            {"action_type": "click", "x": 0, "y": 0, "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])
        self.assertIn("0,0", result["reason"])

    def test_x_out_of_bounds_rejected(self):
        """x beyond screen width should be rejected."""
        result = _validate_action(
            {"action_type": "click", "x": 2000, "y": 500, "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])
        self.assertIn("out of bounds", result["reason"])

    def test_y_out_of_bounds_rejected(self):
        """y beyond screen height should be rejected."""
        result = _validate_action(
            {"action_type": "click", "x": 500, "y": 1200, "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])

    def test_negative_coordinates_rejected(self):
        """Negative coordinates should be rejected."""
        result = _validate_action(
            {"action_type": "click", "x": -10, "y": 50, "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])

    def test_click_at_boundary_valid(self):
        """Click at max valid coordinate should pass."""
        result = _validate_action(
            {"action_type": "click", "x": 1919, "y": 1079, "details": "test"},
            1920, 1080,
        )
        self.assertTrue(result["valid"])

    def test_non_numeric_coordinates_rejected(self):
        """Non-numeric coordinates should be rejected."""
        result = _validate_action(
            {"action_type": "click", "x": "abc", "y": "def", "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])

    def test_null_coordinates_rejected(self):
        """None coordinates should be rejected."""
        result = _validate_action(
            {"action_type": "click", "x": None, "y": None, "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])


class TestInvalidActionProtection(unittest.TestCase):
    """Tests for malformed or invalid model output handling."""

    def test_missing_action_type_rejected(self):
        """Missing action_type should be rejected."""
        result = _validate_action({"details": "test"}, 1920, 1080)
        self.assertFalse(result["valid"])
        self.assertIn("Missing", result["reason"])

    def test_unknown_action_type_rejected(self):
        """Unknown action_type should be rejected."""
        result = _validate_action(
            {"action_type": "teleport", "details": "test"},
            1920, 1080,
        )
        self.assertFalse(result["valid"])
        self.assertIn("Unknown", result["reason"])

    def test_type_without_text_rejected(self):
        """type action with empty details should be rejected."""
        result = _validate_action(
            {"action_type": "type", "details": ""},
            1920, 1080,
        )
        self.assertFalse(result["valid"])

    def test_key_press_without_details_rejected(self):
        """key_press without key name should be rejected."""
        result = _validate_action(
            {"action_type": "key_press", "details": ""},
            1920, 1080,
        )
        self.assertFalse(result["valid"])

    def test_valid_type_action_passes(self):
        """type with text should pass."""
        result = _validate_action(
            {"action_type": "type", "details": "hello world"},
            1920, 1080,
        )
        self.assertTrue(result["valid"])

    def test_valid_key_press_passes(self):
        """key_press with key name should pass."""
        result = _validate_action(
            {"action_type": "key_press", "details": "enter"},
            1920, 1080,
        )
        self.assertTrue(result["valid"])

    def test_valid_wait_passes(self):
        """wait action should always pass."""
        result = _validate_action(
            {"action_type": "wait", "details": "waiting"},
            1920, 1080,
        )
        self.assertTrue(result["valid"])

    def test_valid_done_passes(self):
        """done action should always pass."""
        result = _validate_action(
            {"action_type": "done", "details": "task complete"},
            1920, 1080,
        )
        self.assertTrue(result["valid"])


class TestAppLaunchPattern(unittest.TestCase):
    """Tests for common application launch keyboard patterns."""

    def test_open_calculator_returns_plan(self):
        """'Open Calculator' should return a Win+type+Enter plan."""
        result = _get_app_launch_plan("Open Calculator")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "ACT")
        self.assertEqual(result["action_type"], "key_press")
        self.assertIn("plan", result)
        self.assertEqual(len(result["plan"]), 4)

    def test_launch_chrome_returns_plan(self):
        """'launch chrome' should return a plan."""
        result = _get_app_launch_plan("launch chrome")
        self.assertIsNotNone(result)
        self.assertIn("plan", result)

    def test_start_notepad_returns_plan(self):
        """'start notepad' should return a plan."""
        result = _get_app_launch_plan("start notepad")
        self.assertIsNotNone(result)

    def test_plan_uses_win_key(self):
        """First step should press Windows key."""
        result = _get_app_launch_plan("open paint")
        self.assertEqual(result["plan"][0]["action_type"], "key_press")
        self.assertEqual(result["plan"][0]["details"], "win")

    def test_plan_types_app_name(self):
        """Second step should type the app name."""
        result = _get_app_launch_plan("open notepad")
        self.assertEqual(result["plan"][2]["action_type"], "type")
        self.assertEqual(result["plan"][2]["details"], "notepad")

    def test_plan_presses_enter(self):
        """Last step should press Enter."""
        result = _get_app_launch_plan("open calculator")
        self.assertEqual(result["plan"][3]["action_type"], "key_press")
        self.assertEqual(result["plan"][3]["details"], "enter")

    def test_non_app_task_returns_none(self):
        """Non-app tasks should not trigger app launch pattern."""
        result = _get_app_launch_plan("click the search button")
        self.assertIsNone(result)

    def test_unknown_app_still_works(self):
        """Unknown but reasonable app names should still get a plan."""
        result = _get_app_launch_plan("open myapp")
        self.assertIsNotNone(result)

    def test_very_long_name_rejected(self):
        """Extremely long names shouldn't trigger app launch."""
        result = _get_app_launch_plan("open " + "a" * 50)
        self.assertIsNone(result)

    def test_known_apps_list(self):
        """All known apps should be recognized."""
        for app in _KNOWN_APPS:
            result = _get_app_launch_plan(f"open {app}")
            self.assertIsNotNone(result, f"'open {app}' should trigger app launch")

    # --- Compound task tests ---

    def test_compound_task_extracts_app_and_remaining(self):
        """'Open Calculator and calculate 123 + 456' should split correctly."""
        result = _get_app_launch_plan("Open Calculator and calculate 123 + 456")
        self.assertIsNotNone(result)
        self.assertEqual(result["app_name"], "calculator")
        self.assertEqual(result["remaining_task"], "calculate 123 + 456")

    def test_compound_with_then(self):
        """'open notepad then type hello' should split on 'then'."""
        result = _get_app_launch_plan("open notepad then type hello")
        self.assertIsNotNone(result)
        self.assertEqual(result["app_name"], "notepad")
        self.assertEqual(result["remaining_task"], "type hello")

    def test_compound_with_comma(self):
        """'launch chrome, search for news' should split on comma."""
        result = _get_app_launch_plan("launch chrome, search for news")
        self.assertIsNotNone(result)
        self.assertEqual(result["app_name"], "chrome")
        self.assertEqual(result["remaining_task"], "search for news")

    def test_simple_task_no_remaining(self):
        """'Open Calculator' should have no remaining_task."""
        result = _get_app_launch_plan("Open Calculator")
        self.assertIsNotNone(result)
        self.assertEqual(result["app_name"], "calculator")
        self.assertNotIn("remaining_task", result)

    def test_multi_word_app_name(self):
        """'open visual studio code and write a script' should handle multi-word name."""
        result = _get_app_launch_plan("open visual studio code and write a script")
        self.assertIsNotNone(result)
        self.assertEqual(result["app_name"], "visual studio code")
        self.assertEqual(result["remaining_task"], "write a script")

    def test_unknown_app_with_conjunction(self):
        """'open myapp and do something' should extract unknown app name."""
        result = _get_app_launch_plan("open myapp and do something")
        self.assertIsNotNone(result)
        self.assertEqual(result["app_name"], "myapp")
        self.assertEqual(result["remaining_task"], "do something")

    def test_non_app_task_returns_none_compound(self):
        """Non-app tasks should still return None."""
        result = _get_app_launch_plan("click the search button and type query")
        self.assertIsNone(result)

    def test_malformed_command_returns_none(self):
        """Empty/garbage input should return None."""
        self.assertIsNone(_get_app_launch_plan(""))
        self.assertIsNone(_get_app_launch_plan("hello world"))
        self.assertIsNone(_get_app_launch_plan("123 456"))


class TestMultiStepPlan(unittest.TestCase):
    """Tests for multi-step action plan support."""

    def test_plan_steps_extracted(self):
        """Plan array should be extracted from decision."""
        decision = {
            "action_type": "click",
            "x": 100,
            "y": 200,
            "details": "click start",
            "plan": [
                {"action_type": "type", "details": "hello"},
                {"action_type": "key_press", "details": "enter"},
            ],
        }
        # The plan should be present in the decision
        self.assertIn("plan", decision)
        self.assertEqual(len(decision["plan"]), 2)

    def test_plan_steps_validated(self):
        """Plan steps should be validated before execution."""
        steps = [
            {"action_type": "click", "x": 100, "y": 200, "details": "valid"},
            {"action_type": "click", "x": 0, "y": 0, "details": "invalid"},
            {"action_type": "type", "details": "text"},
        ]
        valid_steps = []
        for step in steps:
            val = _validate_action(step, 1920, 1080)
            if val["valid"]:
                valid_steps.append(step)

        self.assertEqual(len(valid_steps), 2)  # (0,0) step removed


class TestSafetyPreservation(unittest.TestCase):
    """Tests that existing safety restrictions are preserved."""

    def test_forbidden_actions_still_defined(self):
        """All original forbidden actions must remain."""
        self.assertIn("shutdown", FORBIDDEN_ACTIONS)
        self.assertIn("restart", FORBIDDEN_ACTIONS)
        self.assertIn("delete_file", FORBIDDEN_ACTIONS)
        self.assertIn("format", FORBIDDEN_ACTIONS)

    def test_confirmation_required_still_defined(self):
        """All original confirmation-required actions must remain."""
        self.assertIn("close_app", CONFIRMATION_REQUIRED)
        self.assertIn("kill_process", CONFIRMATION_REQUIRED)

    def test_valid_action_types_include_safety(self):
        """Action types should not include forbidden operations."""
        self.assertNotIn("shutdown", VALID_ACTION_TYPES)
        self.assertNotIn("restart", VALID_ACTION_TYPES)
        self.assertNotIn("delete_file", VALID_ACTION_TYPES)

    def test_max_iterations_preserved(self):
        """Iteration limit must remain."""
        self.assertEqual(MAX_ITERATIONS, 10)


class TestKeyActionTypes(unittest.TestCase):
    """Tests for the new key_press action type."""

    def test_key_press_in_valid_types(self):
        """key_press must be in VALID_ACTION_TYPES."""
        self.assertIn("key_press", VALID_ACTION_TYPES)

    def test_all_expected_action_types(self):
        """All expected action types should be present."""
        expected = {"click", "type", "key_press", "scroll", "wait", "done", "fail"}
        self.assertEqual(VALID_ACTION_TYPES, expected)


if __name__ == "__main__":
    unittest.main()
