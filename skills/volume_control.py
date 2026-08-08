"""
ULTRON V3
Volume Control

Cross-platform: delegates all audio operations to the platform adapter.

Windows: uses pycaw (Windows COM audio endpoint) via WindowsAdapter
Linux:   uses pactl (PulseAudio/PipeWire) or amixer (ALSA) via LinuxAdapter
"""

import ultron_platform


def _adapter():
    return ultron_platform.get_platform_adapter()


def _result_str(result: dict, fallback: str) -> str:
    """Extract the user-facing string from an adapter result dict."""
    if result.get("available"):
        if result.get("error"):
            return f"Cannot control volume: {result.get('error')}"
        if not result.get("verified", True):
            return "Volume verification failed, Boss."
        return result.get("result") or fallback
    reason = result.get("reason", "Audio control unavailable on this platform.")
    return f"Cannot control volume: {reason}"


def volume_up():
    return _result_str(_adapter().volume_up(step=0.1), "Volume increased Boss.")


def volume_down():
    return _result_str(_adapter().volume_down(step=0.1), "Volume decreased Boss.")


def mute():
    return _result_str(_adapter().mute(), "Volume muted Boss.")


def unmute():
    return _result_str(_adapter().unmute(), "Volume unmuted Boss.")


def max_volume():
    return _result_str(_adapter().set_volume(1.0), "Maximum volume activated Boss.")


def min_volume():
    return _result_str(_adapter().set_volume(0.0), "Minimum volume activated Boss.")


def set_volume_pct(percent: int):
    try:
        pct = max(0, min(100, int(percent)))
        val = pct / 100.0
        return _result_str(_adapter().set_volume(val), f"Volume set to {pct} percent, Boss.")
    except (ValueError, TypeError):
        return "Cannot set volume: invalid percentage."