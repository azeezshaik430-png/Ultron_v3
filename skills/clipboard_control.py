"""
ULTRON V3
Clipboard Control Skill

Cross-platform clipboard operations via platform adapter.
"""

import ultron_platform


def _adapter():
    return ultron_platform.get_platform_adapter()


def copy_to_clipboard(text: str) -> str:
    """Copy text to system clipboard."""
    if not text:
        return "Nothing to copy, Boss."
    result = _adapter().set_clipboard(text)
    if result.get("available"):
        return f"Copied to clipboard, Boss."
    reason = result.get("reason", "Clipboard unavailable on this platform.")
    return f"Cannot copy to clipboard: {reason}"


def get_clipboard_content() -> str:
    """Get current clipboard content."""
    result = _adapter().get_clipboard()
    if result.get("available"):
        content = result.get("result", "")
        if content:
            return f"Clipboard contains: {content}"
        return "Clipboard is empty, Boss."
    reason = result.get("reason", "Clipboard unavailable on this platform.")
    return f"Cannot read clipboard: {reason}"
