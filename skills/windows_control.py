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

    os.system(
        "shutdown /s /t 5"
    )

    return "Shutting down computer Boss."



def restart_pc():

    os.system(
        "shutdown /r /t 5"
    )

    return "Restarting computer Boss."



def sleep_pc():

    subprocess.run(
        [
            "rundll32.exe",
            "powrprof.dll,SetSuspendState",
            "0,1,0"
        ]
    )

    return "Going to sleep mode Boss."