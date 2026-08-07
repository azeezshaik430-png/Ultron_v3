"""
ULTRON V3
Windows Control Skill
"""

import os
import subprocess



def lock_pc():

    os.system(
        "rundll32.exe user32.dll,LockWorkStation"
    )

    return "Locking computer Boss."



def open_settings():

    os.system(
        "start ms-settings:"
    )

    return "Opening Windows Settings."



def shutdown_pc():
    """
    Execute Windows OS Shutdown sequence.
    STRICT TOKEN-BASED INTERNAL AUTHORIZATION SECURITY GUARD:
    Verifies internally that:
    1. session.pending_confirmation exists
    2. pending_confirmation.action == 'shutdown_pc'
    3. pending_confirmation.validated == True
    4. Current time <= pending_confirmation.expires_at
    """
    from core.session import session
    from core.logger import logger
    from core.config import config
    import datetime
    import time

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
        logger.error("SECURITY VIOLATION: Execution path attempted to call shutdown_pc() without valid token authorization!")
        try:
            log_dir = config.LOGS_DIR
            os.makedirs(log_dir, exist_ok=True)
            sec_log_path = os.path.join(log_dir, "security.log")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cmd_str = pending.get("command", "shutdown_pc") if pending and isinstance(pending, dict) else "shutdown_pc"
            entry = f"[{timestamp}] Command: '{cmd_str}' | Status: 'Unauthorized Shutdown Blocked'\n"
            with open(sec_log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass
        return "Security block: Unauthorized Shutdown Blocked"

    # REPLAY PROTECTION: Completely destroy token confirmation object IMMEDIATELY before executing OS shutdown
    session.clear_pending_confirmation()

    os.system(
        "shutdown /s /t 5"
    )

    return "Shutting down computer Boss."



def restart_pc():

    os.system(
        "shutdown /r /t 5"
    )

    return "Restarting computer Boss."



def sign_out_pc():
    """Sign out of Windows session."""
    os.system("shutdown /l")
    return "Signing out Boss."


def sleep_pc():

    subprocess.run(
        [
            "rundll32.exe",
            "powrprof.dll,SetSuspendState",
            "0,1,0"
        ]
    )

    return "Going to sleep mode Boss."


# ==========================================
# PERMANENTLY UNSUPPORTED DESTRUCTIVE ACTIONS
# Factory Reset, Format Drive, and Delete All Files
# are intentionally unsupported for security.
# No execution paths or stubs exist for these actions.
# ==========================================