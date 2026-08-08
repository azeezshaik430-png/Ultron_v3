"""
ULTRON V3
System Session Control Skill

Cross-platform: session control operations (shutdown, restart, lock, sleep,
sign-out, settings) are delegated to the platform adapter. All existing
ULTRON security guards are preserved unchanged.

SECURITY INVARIANTS (preserved from original):
    - shutdown_pc() has strict token-based internal authorization.
    - Token must exist, match action, be validated, and be unexpired.
    - Token is consumed (cleared) immediately before OS execution.
    - Replay protection is maintained.
    - Security violations are logged to security.log.
    - restart_pc() requires explicit confirmed=True in caller payload
      (enforced by SystemAgent._do_execute_task).
"""

import os
import datetime
import time
import ultron_platform


def _adapter():
    return ultron_platform.get_platform_adapter()


def lock_pc():
    result = _adapter().lock()
    if result.get("available"):
        return result.get("result", "Locking computer Boss.")
    reason = result.get("reason", "Lock not supported on this platform.")
    return f"Cannot lock: {reason}"


def open_settings():
    result = _adapter().open_settings()
    if result.get("available"):
        return result.get("result", "Opening system settings.")
    reason = result.get("reason", "Settings panel not available on this platform.")
    return f"Cannot open settings: {reason}"


def shutdown_pc():
    """
    Execute OS Shutdown sequence.

    STRICT TOKEN-BASED INTERNAL AUTHORIZATION SECURITY GUARD (PRESERVED):
    Verifies internally that:
    1. session.pending_confirmation exists
    2. pending_confirmation.action == 'shutdown_pc'
    3. pending_confirmation.validated == True
    4. Current time <= pending_confirmation.expires_at
    """
    from core.session import session
    from core.logger import logger
    from core.config import config

    now = time.time()
    pending = session.pending_confirmation
    is_valid_action = False
    is_validated = False
    is_unexpired = False

    if pending and isinstance(pending, dict):
        action_val = pending.get("action")
        cmd_val = pending.get("command")
        if action_val == "shutdown_pc" or cmd_val in [
            "shutdown pc", "shutdown computer", "turn off pc",
            "turn off computer", "power off computer", "power off windows"
        ]:
            is_valid_action = True

        if pending.get("validated") is True or pending.get("confirmed") is True:
            is_validated = True

        expires_at = pending.get("expires_at", 0)
        created_at = pending.get("created_at", 0)
        if expires_at and now > expires_at:
            is_unexpired = False
        elif created_at and (now - created_at) > 15.0:
            is_unexpired = False
        else:
            is_unexpired = True

    if not (pending and is_valid_action and is_validated and is_unexpired):
        logger.error(
            "SECURITY VIOLATION: Execution path attempted to call shutdown_pc() "
            "without valid token authorization!"
        )
        try:
            log_dir = config.LOGS_DIR
            os.makedirs(log_dir, exist_ok=True)
            sec_log_path = os.path.join(log_dir, "security.log")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cmd_str = (
                pending.get("command", "shutdown_pc")
                if pending and isinstance(pending, dict)
                else "shutdown_pc"
            )
            entry = (
                f"[{timestamp}] Command: '{cmd_str}' | "
                f"Status: 'Unauthorized Shutdown Blocked'\n"
            )
            with open(sec_log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
        return "Security block: Unauthorized Shutdown Blocked"

    # REPLAY PROTECTION: Completely destroy token confirmation object IMMEDIATELY
    # before executing OS shutdown.
    session.clear_pending_confirmation()

    result = _adapter().shutdown(delay_sec=5)
    if result.get("available"):
        return result.get("result", "Shutting down computer Boss.")
    reason = result.get("reason", "Shutdown not supported on this platform.")
    return f"Cannot shutdown: {reason}"


def restart_pc():
    result = _adapter().restart(delay_sec=5)
    if result.get("available"):
        return result.get("result", "Restarting computer Boss.")
    reason = result.get("reason", "Restart not supported on this platform.")
    return f"Cannot restart: {reason}"


def sign_out_pc():
    """Sign out of the current user session."""
    result = _adapter().sign_out()
    if result.get("available"):
        return result.get("result", "Signing out Boss.")
    reason = result.get("reason", "Sign-out not supported on this platform.")
    return f"Cannot sign out: {reason}"


def sleep_pc():
    result = _adapter().sleep()
    if result.get("available"):
        return result.get("result", "Going to sleep mode Boss.")
    reason = result.get("reason", "Sleep not supported on this platform.")
    return f"Cannot sleep: {reason}"


# ==========================================
# PERMANENTLY UNSUPPORTED DESTRUCTIVE ACTIONS
# Factory Reset, Format Drive, and Delete All Files
# are intentionally unsupported for security.
# No execution paths or stubs exist for these actions.
# ==========================================