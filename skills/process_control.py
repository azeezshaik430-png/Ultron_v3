"""
ULTRON V3
Process Control Skill

Cross-platform process management using psutil.
"""

import psutil
from typing import Dict, Any, List


def list_processes(filter_name: str = None, top_n: int = 10) -> str:
    """List running processes, optionally filtered by name."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            name = info.get("name", "")
            if filter_name and filter_name.lower() not in name.lower():
                continue
            processes.append({
                "pid": info.get("pid", 0),
                "name": name,
                "cpu": round(info.get("cpu_percent", 0), 1),
                "mem": round(info.get("memory_percent", 0), 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not processes:
        return f"No processes found{' matching ' + filter_name if filter_name else ''}."

    # Sort by memory usage
    processes.sort(key=lambda x: x["mem"], reverse=True)
    processes = processes[:top_n]

    lines = [f"Top {len(processes)} processes:"]
    for p in processes:
        lines.append(f"  PID {p['pid']}: {p['name']} (CPU: {p['cpu']}%, MEM: {p['mem']}%)")
    return "\n".join(lines)


def find_process(name: str) -> List[Dict[str, Any]]:
    """Find processes matching a name."""
    matches = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            if name.lower() in info.get("name", "").lower():
                matches.append({
                    "pid": info.get("pid", 0),
                    "name": info.get("name", ""),
                    "cpu": round(info.get("cpu_percent", 0), 1),
                    "mem": round(info.get("memory_percent", 0), 1),
                    "status": info.get("status", "unknown"),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return matches


def kill_process(name: str, force: bool = False) -> str:
    """Kill all processes matching a name."""
    matches = find_process(name)
    if not matches:
        return f"No running process found matching '{name}'."

    killed = 0
    for proc_info in matches:
        try:
            proc = psutil.Process(proc_info["pid"])
            if force:
                proc.kill()
            else:
                proc.terminate()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    action = "Force killed" if force else "Terminated"
    return f"{action} {killed} process(es) matching '{name}'."


def get_process_info(name: str) -> str:
    """Get detailed info about a process."""
    matches = find_process(name)
    if not matches:
        return f"No process found matching '{name}'."

    lines = [f"Found {len(matches)} process(es) matching '{name}':"]
    for p in matches:
        lines.append(
            f"  PID {p['pid']}: {p['name']} | "
            f"CPU: {p['cpu']}% | MEM: {p['mem']}% | Status: {p['status']}"
        )
    return "\n".join(lines)
