"""
ULTRON V3
Intent Engine v2.0
"""

OPEN_WORDS = {
    "open",
    "launch",
    "start",
    "run",
    "execute"
}

CLOSE_WORDS = {
    "close",
    "exit",
    "quit"
}

SEARCH_WORDS = {
    "search",
    "find",
    "look"
}

SYSTEM_WORDS = {
    "status",
    "battery",
    "time",
    "date"
}


def clean_target(command: str, words) -> str:
    parts = command.split()

    cleaned = [
        word
        for word in parts
        if word not in words
    ]

    return " ".join(cleaned).strip()


def detect_intent(command: str):

    command = command.lower().strip()

    words = command.split()

    # OPEN
    for word in words:
        if word in OPEN_WORDS:
            return {
                "intent": "OPEN_APP",
                "target": clean_target(command, OPEN_WORDS)
            }

    # CLOSE
    for word in words:
        if word in CLOSE_WORDS:
            return {
                "intent": "CLOSE_APP",
                "target": clean_target(command, CLOSE_WORDS)
            }

    # SEARCH
    for word in words:
        if word in SEARCH_WORDS:
            return {
                "intent": "SEARCH",
                "target": clean_target(command, SEARCH_WORDS)
            }

    # SYSTEM
    for word in words:
        if word in SYSTEM_WORDS:
            return {
                "intent": "SYSTEM",
                "target": command
            }

    return {
        "intent": "CHAT",
        "target": command
    }