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
    from core.session import session
    if not _validate_security_token("lock_pc"):
        return "Security block: Unauthorized Lock Blocked"
    session.clear_pending_confirmation()
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


def _validate_security_token(expected_action: str) -> bool:
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
        
        # Validate action matches expected
        if action_val == expected_action:
            is_valid_action = True
        elif expected_action == "shutdown_pc" and cmd_val in [
            "shutdown pc", "shutdown computer", "turn off pc",
            "turn off computer", "power off computer", "power off windows",
            "shutdown my pc", "power off pc"
        ]:
            is_valid_action = True
        elif expected_action == "restart_pc" and cmd_val in [
            "restart pc", "restart computer", "reboot pc", "restart my pc", "reboot computer"
        ]:
            is_valid_action = True
        elif expected_action == "sign_out_pc" and cmd_val in [
            "sign out", "log out", "sign me out", "sign out my pc", "log out my pc"
        ]:
            is_valid_action = True
        elif expected_action == "sleep_pc" and cmd_val in [
            "sleep pc", "sleep computer", "sleep my pc", "put pc to sleep", "put computer to sleep"
        ]:
            is_valid_action = True
        elif expected_action == "lock_pc" and cmd_val in [
            "lock pc", "lock computer", "lock my pc"
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
            f"SECURITY VIOLATION: Execution path attempted to call {expected_action}() "
            "without valid token authorization!"
        )
        try:
            log_dir = config.LOGS_DIR
            os.makedirs(log_dir, exist_ok=True)
            sec_log_path = os.path.join(log_dir, "security.log")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cmd_str = (
                pending.get("command", expected_action)
                if pending and isinstance(pending, dict)
                else expected_action
            )
            entry = (
                f"[{timestamp}] Command: '{cmd_str}' | "
                f"Status: 'Unauthorized {expected_action} Blocked'\n"
            )
            with open(sec_log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
        return False
        
    return True


def shutdown_pc():
    """
    Execute OS Shutdown sequence.
    """
    from core.session import session
    
    if not _validate_security_token("shutdown_pc"):
        return "Security block: Unauthorized Shutdown Blocked"

    # REPLAY PROTECTION: Completely destroy token confirmation object IMMEDIATELY
    session.clear_pending_confirmation()

    result = _adapter().shutdown(delay_sec=5)
    if result.get("available"):
        return result.get("result", "Shutting down computer Boss.")
    reason = result.get("reason", "Shutdown not supported on this platform.")
    return f"Cannot shutdown: {reason}"


def restart_pc():
    from core.session import session
    
    if not _validate_security_token("restart_pc"):
        return "Security block: Unauthorized Restart Blocked"

    session.clear_pending_confirmation()

    result = _adapter().restart(delay_sec=5)
    if result.get("available"):
        return result.get("result", "Restarting computer Boss.")
    reason = result.get("reason", "Restart not supported on this platform.")
    return f"Cannot restart: {reason}"


def sign_out_pc():
    """Sign out of the current user session."""
    from core.session import session
    
    if not _validate_security_token("sign_out_pc"):
        return "Security block: Unauthorized Sign Out Blocked"

    session.clear_pending_confirmation()

    result = _adapter().sign_out()
    if result.get("available"):
        return result.get("result", "Signing out Boss.")
    reason = result.get("reason", "Sign-out not supported on this platform.")
    return f"Cannot sign out: {reason}"


def sleep_pc():
    from core.session import session
    if not _validate_security_token("sleep_pc"):
        return "Security block: Unauthorized Sleep Blocked"
    session.clear_pending_confirmation()
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