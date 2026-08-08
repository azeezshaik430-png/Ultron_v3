"""
ULTRON V3
System Control Skill with Dynamic Hardware Detection
"""

import datetime
import os
import platform
import subprocess
import psutil
from typing import List
from core.logger import logger


def get_time() -> str:
    now = datetime.datetime.now()
    return f"The time is {now.strftime('%I:%M %p')}"


def get_date() -> str:
    today = datetime.datetime.now()
    return f"Today is {today.strftime('%d %B %Y')}"


def get_battery() -> str:
    battery = psutil.sensors_battery()
    if battery:
        percent = battery.percent
        status = "charging" if battery.power_plugged else "not charging"
        return f"Battery is {percent}% and {status}"
    return "Battery information unavailable"


def system_status() -> str:
    return (
        "All systems are online Boss. "
        "Voice, memory and command systems are working."
    )


def get_gpus() -> List[str]:
    """Dynamically detect all installed video controllers/GPUs without hardcoding."""
    gpus = []
    sys_name = platform.system()
    if sys_name == "Windows":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"]
            out = subprocess.check_output(cmd, text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
            gpus = [line.strip() for line in out.splitlines() if line.strip()]
        except Exception as err:
            logger.debug(f"[system_control] WMI GPU query notice: {err}")
    elif sys_name == "Linux":
        try:
            out = subprocess.check_output(["lspci"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if any(k in line for k in ["VGA", "3D", "Display"]):
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        gpus.append(parts[-1].strip())
        except Exception as err:
            logger.debug(f"[system_control] lspci GPU query notice: {err}")
    return gpus


def get_cpu_info() -> str:
    """Dynamically detect CPU name and core layout."""
    sys_name = platform.system()
    cpu_name = ""
    if sys_name == "Windows":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"]
            cpu_name = subprocess.check_output(cmd, text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
        except Exception:
            pass
    elif sys_name == "Linux":
        try:
            out = subprocess.check_output(["lscpu"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if "Model name:" in line:
                    cpu_name = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

    if not cpu_name:
        cpu_name = platform.processor() or "Unavailable"

    try:
        cores_phys = psutil.cpu_count(logical=False) or "Unavailable"
        cores_log = psutil.cpu_count(logical=True) or "Unavailable"
        usage = psutil.cpu_percent(interval=0.1)
        return f"{cpu_name} ({cores_phys} Cores, {cores_log} Threads @ {usage}% usage)"
    except Exception:
        return cpu_name


def get_system_info() -> str:
    """
    Dynamically query system hardware specifications from OS APIs.
    Never hardcodes hardware names or brand values.
    """
    try:
        os_info = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"
    except Exception:
        os_info = "Unavailable"

    try:
        hostname = platform.node() or "Unavailable"
    except Exception:
        hostname = "Unavailable"

    try:
        cpu_str = get_cpu_info()
    except Exception:
        cpu_str = "Unavailable"

    try:
        gpus = get_gpus()
        gpu_str = ", ".join(gpus) if gpus else "Unavailable"
    except Exception:
        gpu_str = "Unavailable"

    try:
        mem = psutil.virtual_memory()
        ram_total_gb = round(mem.total / (1024 ** 3), 2)
        ram_used_gb = round(mem.used / (1024 ** 3), 2)
        ram_str = f"{ram_total_gb} GB ({ram_used_gb} GB used, {mem.percent}% memory used)"
    except Exception:
        ram_str = "Unavailable"

    try:
        root_path = "C:\\" if platform.system() == "Windows" else "/"
        disk = psutil.disk_usage(root_path)
        disk_total_gb = round(disk.total / (1024 ** 3), 2)
        disk_free_gb = round(disk.free / (1024 ** 3), 2)
        disk_str = f"{disk_total_gb} GB ({disk_free_gb} GB free)"
    except Exception:
        disk_str = "Unavailable"

    try:
        bat = psutil.sensors_battery()
        if bat:
            p_status = "charging" if bat.power_plugged else "not charging"
            bat_str = f"{bat.percent}% ({p_status})"
        else:
            bat_str = "Desktop / No battery"
    except Exception:
        bat_str = "Unavailable"

    return (
        f"Here are your verified system hardware details:\n"
        f"• OS: {os_info}\n"
        f"• Hostname: {hostname}\n"
        f"• CPU: {cpu_str}\n"
        f"• GPU(s): {gpu_str}\n"
        f"• Memory (RAM): {ram_str}\n"
        f"• Storage (Disk): {disk_str}\n"
        f"• Battery: {bat_str}"
    )


def get_disk_info(target_drive: str = None) -> str:
    """
    Dynamically query storage drive specifications using OS APIs.
    Detects presence of C:, D:, E: or target drive dynamically. Never invents drive data.
    """
    sys_name = platform.system()
    if target_drive:
        clean_drive = target_drive.strip().upper().replace(":", "").replace("\\", "")
        drive_path = f"{clean_drive}:\\" if sys_name == "Windows" else f"/{clean_drive.lower()}"
        if os.path.exists(drive_path):
            try:
                usage = psutil.disk_usage(drive_path)
                total_gb = round(usage.total / (1024 ** 3), 2)
                free_gb = round(usage.free / (1024 ** 3), 2)
                used_gb = round(usage.used / (1024 ** 3), 2)
                return (
                    f"Storage details for Drive {clean_drive}:\n"
                    f"• Total Space: {total_gb} GB\n"
                    f"• Free Space: {free_gb} GB\n"
                    f"• Used Space: {used_gb} GB ({usage.percent}% used)"
                )
            except Exception as err:
                return f"Drive {clean_drive}: is present but details are Unavailable."
        else:
            return f"Drive {clean_drive}: is not present on this machine."

    # Enumerate all present drives
    drives = []
    if sys_name == "Windows":
        for letter in ["C", "D", "E", "F"]:
            p = f"{letter}:\\"
            if os.path.exists(p):
                try:
                    usage = psutil.disk_usage(p)
                    total_gb = round(usage.total / (1024 ** 3), 2)
                    free_gb = round(usage.free / (1024 ** 3), 2)
                    used_gb = round(usage.used / (1024 ** 3), 2)
                    drives.append(f"• Drive {letter}: {total_gb} GB total ({free_gb} GB free, {used_gb} GB used)")
                except Exception:
                    drives.append(f"• Drive {letter}: Unavailable")
    else:
        try:
            usage = psutil.disk_usage("/")
            total_gb = round(usage.total / (1024 ** 3), 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
            used_gb = round(usage.used / (1024 ** 3), 2)
            drives.append(f"• Root (/): {total_gb} GB total ({free_gb} GB free, {used_gb} GB used)")
        except Exception:
            drives.append("• Root (/): Unavailable")

    if not drives:
        return "Storage information is Unavailable."
    return "Storage Drive Status:\n" + "\n".join(drives)