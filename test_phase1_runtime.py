"""
ULTRON V3 - Phase 1 Runtime Verification & Stabilization Suite
Tests Steps 2 through 8 systematically.
"""

import os
import time
import json
from unittest.mock import patch, MagicMock

from core.config import config
from core.session import session
from core.logger import logger
from brain.orchestrator import orchestrator
import brain.memory as memory_sys
import skills.windows_control as win_control


def test_step2_startup():
    print("\n--- STEP 2: STARTUP VERIFICATION ---")
    session.reset()
    assert session.is_authenticated is False, "session authentication must reset to False on startup"
    assert session.pending_confirmation is None, "pending_confirmation must be None on startup"
    assert logger is not None, "logger must be initialized"
    assert orchestrator is not None, "orchestrator must be initialized"
    print("✅ Step 2 Startup Verification Passed!")


def test_step3_voice_authentication():
    print("\n--- STEP 3: VOICE AUTHENTICATION VERIFICATION ---")
    session.reset()

    # 1. Startup -> Unauthenticated
    assert session.is_authenticated is False

    # 2. Voice Auth Passed -> Authenticated & Active Mode
    session.set_auth(True)
    session.enter_active()
    assert session.is_authenticated is True
    assert session.is_active_mode is True
    assert session.is_sleeping is False

    # 3. Sleep -> Active Mode (No re-verification required)
    session.enter_sleep()
    assert session.is_sleeping is True
    assert session.is_active_mode is False
    assert session.is_authenticated is True  # Auth preserved in sleep

    session.enter_active()  # Wake up
    assert session.is_active_mode is True
    assert session.is_authenticated is True  # Still authenticated without re-verification

    # 4. Logout -> Unauthenticated & Sleep
    orchestrator.process_command("logout")
    assert session.is_authenticated is False
    assert session.is_sleeping is True
    assert session.is_active_mode is False
    print("✅ Step 3 Voice Authentication Verification Passed!")


def test_step4_memory():
    print("\n--- STEP 4: MEMORY VERIFICATION ---")
    session.reset()
    session.set_auth(True)
    session.enter_active()

    # Save test memories
    memory_sys.save_memory({
        "name": "Azeez",
        "laptop": "Dell XPS",
        "phone": "iPhone 15 Pro",
        "project": "ULTRON V3",
        "likes": "Coding and AI"
    })

    memory_commands = [
        ("what is my name", "Azeez"),
        ("what is my laptop", "Dell XPS"),
        ("what is my phone", "iPhone 15 Pro"),
        ("what is my project", "ULTRON V3"),
        ("show my memories", "Boss, I remember"),
    ]

    with patch("brain.orchestrator.llm_manager.ask") as mock_llm:
        for cmd, expected in memory_commands:
            result = orchestrator.process_command(cmd)
            assert expected in result, f"Expected '{expected}' in response to '{cmd}', got '{result}'"
            assert mock_llm.call_count == 0, f"LLM must NEVER be called for memory query '{cmd}'"

    print("✅ Step 4 Memory Verification Passed (Zero LLM Calls)!")


def test_step5_skills():
    print("\n--- STEP 5: SKILL VERIFICATION ---")
    session.reset()
    session.set_auth(True)
    session.enter_active()

    skills_to_test = [
        ("open notepad", "open_app"),
        ("close notepad", "close_app"),
        ("open chrome", "open_app"),
        ("close chrome", "close_app"),
        ("open calculator", "open_app"),
        ("close calculator", "close_app"),
    ]

    for cmd, skill_func_name in skills_to_test:
        with patch(f"brain.orchestrator.{skill_func_name}") as mock_skill:
            mock_skill.return_value = True
            result = orchestrator.process_command(cmd)
            assert mock_skill.call_count == 1, f"Skill handler '{skill_func_name}' was not called for command '{cmd}'"

    print("✅ Step 5 Skill Routing Verification Passed!")


def test_step6_security():
    print("\n--- STEP 6: SECURITY VERIFICATION ---")
    session.reset()
    session.set_auth(True)
    session.enter_active()

    from skills.windows_control import shutdown_pc

    # 1. shutdown ultron -> ULTRON exits, Windows running
    with patch("brain.orchestrator.shutdown_pc") as mock_win_shutdown:
        res = orchestrator.process_command("shutdown ultron")
        assert "Shutting down ULTRON" in res or "Goodbye" in res
        assert mock_win_shutdown.call_count == 0, "Windows shutdown must NOT be called for 'shutdown ultron'"

    # TEST CASE 1: Shutdown without confirmation -> Expected: Blocked
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        r1 = orchestrator.process_command("shutdown pc")
        expected_prompt = "Are you sure, Boss?\nYou requested to shut down your computer.\nPlease say 'Yes' to continue or 'Cancel' to abort."
        assert r1 == expected_prompt, f"Expected '{expected_prompt}', got '{r1}'"
        assert mock_os_sys.call_count == 0, "Shutdown MUST NOT execute without confirmation"

    # TEST CASE 2: Shutdown after confirmation -> Expected: Success
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        orchestrator.process_command("shutdown pc")
        r2 = orchestrator.process_command("yes")
        expected_confirm = "Confirmation received.\nShutting down your computer.\nGoodbye, Boss."
        assert r2 == expected_confirm, f"Expected '{expected_confirm}', got '{r2}'"
        assert mock_os_sys.call_count == 1, "Shutdown MUST execute after confirmation"

    # TEST CASE 3: Cancelled confirmation -> Expected: Blocked
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        orchestrator.process_command("shutdown pc")
        r_cancel = orchestrator.process_command("cancel")
        assert r_cancel == "Shutdown cancelled, Boss."
        assert mock_os_sys.call_count == 0, "Shutdown MUST NOT execute after cancel"

    # TEST CASE 4: Expired confirmation (>15s timeout) -> Expected: Blocked
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        orchestrator.process_command("shutdown pc")
        session.pending_confirmation["created_at"] = time.time() - 16.0
        session.pending_confirmation["expires_at"] = time.time() - 1.0
        r_timeout = orchestrator.process_command("yes")
        assert r_timeout == "Shutdown request timed out.\nOperation cancelled."
        assert mock_os_sys.call_count == 0, "Shutdown MUST NOT execute after timeout"

    # TEST CASE 5: Random direct call to shutdown_pc() without confirmation -> Expected: Blocked
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        guard_res = shutdown_pc()
        assert "Security block" in guard_res
        assert mock_os_sys.call_count == 0, "Direct call to shutdown_pc() MUST be blocked"

    # TEST CASE 6: Replay attack (Reuse confirmation twice) -> Expected: 1st succeeds, 2nd blocked
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        orchestrator.process_command("shutdown pc")
        # First execution via Orchestrator succeeds and invalidates pending confirmation (replay protection)
        first_res = orchestrator.process_command("yes")
        assert "Confirmation received" in first_res
        assert mock_os_sys.call_count == 1

        # Second execution attempt (replay attack) MUST be blocked
        second_res = shutdown_pc()
        assert "Security block" in second_res
        assert mock_os_sys.call_count == 1, "Replay attack MUST be blocked"

    # TEST CASE 7: Multiple confirmations -> Old confirmation invalid, newest confirmation active
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        orchestrator.process_command("shutdown pc")
        id1 = session.pending_confirmation["id"]
        orchestrator.process_command("shutdown computer")
        id2 = session.pending_confirmation["id"]
        assert id1 != id2, "New confirmation MUST generate a unique token ID"
        r_confirm = orchestrator.process_command("yes")
        assert "Confirmation received" in r_confirm
        assert mock_os_sys.call_count == 1

    # TEST CASE 8: TTS still speaking -> Shutdown waits until speech completes
    session.reset()
    speech_events = []
    def mock_speak(text):
        speech_events.append(f"SPEAK: {text}")

    def mock_sys(cmd):
        speech_events.append(f"SYSTEM: {cmd}")

    with patch("voice.speech_output.speak", side_effect=mock_speak):
        with patch("skills.windows_control.os.system", side_effect=mock_sys):
            orchestrator.process_command("shutdown pc")
            orchestrator.process_command("yes")
            assert len(speech_events) == 2
            assert "SPEAK:" in speech_events[0], "Speech MUST happen before Windows shutdown call"
            assert "SYSTEM:" in speech_events[1], "Windows shutdown call MUST happen after speech finishes"

    # Additional Test: Unrelated command while confirmation pending -> Expected: Cancelled & Execute New
    session.reset()
    with patch("skills.windows_control.os.system") as mock_os_sys:
        with patch("skills.app_control.open_app", return_value=True):
            orchestrator.process_command("shutdown pc")
            r_unrelated = orchestrator.process_command("open chrome")
            assert "Shutdown request cancelled." in r_unrelated
            assert "Opening chrome" in r_unrelated
            assert mock_os_sys.call_count == 0

    # Other Guarded Commands: Restart PC, Lock PC, Sign Out
    security_cmds = ["restart pc", "lock pc", "sign out"]
    for scmd in security_cmds:
        session.reset()
        with patch("skills.windows_control.os.system") as mock_os_sys:
            r1 = orchestrator.process_command(scmd)
            assert "Are you sure, Boss?" in r1
            r2 = orchestrator.process_command("yes")
            assert "Confirmation received" in r2
            assert mock_os_sys.call_count == 1

    print("✅ Step 6 Security Verification Passed!")


def test_step7_security_log():
    print("\n--- STEP 7: SECURITY LOG VERIFICATION ---")
    log_file = os.path.join(config.LOGS_DIR, "security.log")
    assert os.path.exists(log_file), "logs/security.log must exist"

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) > 0
        for line in lines:
            # Must strictly contain timestamp, command, status
            assert "[" in line and "]" in line and "Command:" in line and "Status:" in line
            # Must NEVER contain sensitive fields
            assert "is_authenticated" not in line
            assert "voice" not in line
            assert "memory" not in line
            assert "payload" not in line

    print("✅ Step 7 Security Log Verification Passed!")


def test_step8_shutdown():
    print("\n--- STEP 8: SHUTDOWN VERIFICATION ---")
    session.set_auth(True)
    session.save()

    # Simulate exit sequence
    session.reset()
    assert session.is_authenticated is False
    assert session.pending_confirmation is None
    assert session.is_active_mode is False

    # Verify session.json on disk does NOT contain auth or confirmation
    session_file = os.path.join("data", "session.json")
    if os.path.exists(session_file):
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "is_authenticated" not in data
            assert "pending_confirmation" not in data

    print("✅ Step 8 Clean Shutdown Sequence Verification Passed!")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING ULTRON V3 PHASE 1 RUNTIME VERIFICATION")
    print("==================================================")
    test_step2_startup()
    test_step3_voice_authentication()
    test_step4_memory()
    test_step5_skills()
    test_step6_security()
    test_step7_security_log()
    test_step8_shutdown()
    print("\n🎉 ALL PHASE 1 RUNTIME VERIFICATION TESTS PASSED SUCCESSFULLY!")
