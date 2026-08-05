"""
ULTRON V3
Intent Detection
"""

def detect_intent(command: str):

    command = command.lower()

    if "open" in command:
        return {
            "intent": "OPEN_APP",
            "target": command.replace("open", "").strip()
        }

    if "close" in command:
        return {
            "intent": "CLOSE_APP",
            "target": command.replace("close", "").strip()
        }

    return {
        "intent": "CHAT",
        "target": command
    }