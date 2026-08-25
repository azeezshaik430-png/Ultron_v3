"""
ULTRON V3
Intent Engine v3.0

Expanded intent detection with 12 categories, confidence scoring,
and compound intent support.
"""

from typing import Dict, Any, List, Tuple

# Intent Categories & Trigger Words
INTENT_TRIGGERS = {
    "OPEN_APP": {
        "words": {"open", "launch", "start", "run", "execute"},
        "phrases": ["open up", "fire up"],
        "confidence": 0.8,
    },
    "CLOSE_APP": {
        "words": {"close", "exit", "quit", "kill"},
        "phrases": ["close down", "shut down"],
        "confidence": 0.8,
    },
    "BROWSER": {
        "words": set(),
        "phrases": [
            "go to", "navigate to", "visit", "open website",
            "open youtube", "open google", "open github",
            "go back", "come back", "back",
            "play first", "play second", "play third",
            "close browser", "close tab", "close page",
            "open channel", "search for",
        ],
        "confidence": 0.85,
    },
    "WEB_SEARCH": {
        "words": set(),
        "phrases": [
            "search the web", "search online", "search internet",
            "google for", "google search", "look up",
            "find online", "what is", "who is", "tell me about",
        ],
        "confidence": 0.8,
    },
    "VISION": {
        "words": set(),
        "phrases": [
            "look at my screen", "what is on my screen",
            "read my screen", "analyze my screen",
            "describe my screen", "take a screenshot",
            "screenshot", "capture screen",
            "camera capture", "take a picture",
        ],
        "confidence": 0.85,
    },
    "VOLUME": {
        "words": set(),
        "phrases": [
            "volume up", "volume down", "increase volume",
            "decrease volume", "mute", "unmute",
            "set volume", "max volume", "min volume",
        ],
        "confidence": 0.9,
    },
    "SESSION_CONTROL": {
        "words": set(),
        "phrases": [
            "shutdown", "restart", "reboot", "lock pc",
            "lock computer", "sleep pc", "sleep computer",
            "sign out", "log out", "open settings",
        ],
        "confidence": 0.85,
    },
    "MEMORY": {
        "words": set(),
        "phrases": [
            "remember that", "my name is", "i like",
            "my favorite", "recall", "what do you remember",
            "forget", "clear memories",
        ],
        "confidence": 0.75,
    },
    "SYSTEM": {
        "words": {"status", "battery", "time", "date", "specs", "hardware"},
        "phrases": [
            "system status", "system info", "system details",
            "what time", "what date", "battery status",
            "disk info", "storage status",
        ],
        "confidence": 0.7,
    },
    "RESEARCH": {
        "words": set(),
        "phrases": ["research", "investigate", "conduct research", "research on"],
        "confidence": 0.7,
    },
    "PLANNING": {
        "words": set(),
        "phrases": ["create execution plan", "build plan for", "plan"],
        "confidence": 0.6,
    },
    "SESSION_REPLY": {
        "words": set(),
        "phrases": [
            "yes", "no", "cancel", "confirm", "proceed",
            "do it", "sure", "ok", "okay", "never mind",
        ],
        "confidence": 0.5,
    },
}


def detect_intent(command: str) -> Dict[str, Any]:
    """Detect intent with confidence scoring and compound support."""
    command = command.lower().strip()
    words = command.split()
    detected_intents: List[Tuple[str, float]] = []

    for intent, config in INTENT_TRIGGERS.items():
        score = 0.0
        for word in words:
            if word in config["words"]:
                score = max(score, config["confidence"])
        for phrase in config["phrases"]:
            if phrase in command:
                score = max(score, config["confidence"] + 0.1)
        if score > 0:
            detected_intents.append((intent, min(score, 1.0)))

    detected_intents.sort(key=lambda x: x[1], reverse=True)

    if not detected_intents:
        return {"intent": "CHAT", "target": command, "confidence": 0.3, "compound": False, "all_intents": ["CHAT"]}

    primary = detected_intents[0]
    is_compound = len(detected_intents) > 1 and detected_intents[1][1] > 0.6

    return {
        "intent": primary[0],
        "target": _extract_target(command, primary[0]),
        "confidence": primary[1],
        "compound": is_compound,
        "all_intents": [i[0] for i in detected_intents],
    }


def _extract_target(command: str, intent: str) -> str:
    trigger_words = INTENT_TRIGGERS.get(intent, {}).get("words", set())
    phrases = INTENT_TRIGGERS.get(intent, {}).get("phrases", [])
    target = command
    for phrase in sorted(phrases, key=len, reverse=True):
        target = target.replace(phrase, "")
    words = target.split()
    cleaned = [w for w in words if w not in trigger_words]
    target = " ".join(cleaned).strip()
    fillers = {"please", "can", "you", "could", "would", "the", "a", "an", "my", "me"}
    words = target.split()
    cleaned = [w for w in words if w not in fillers]
    target = " ".join(cleaned).strip()
    return target if target else command


def clean_target(command: str, words) -> str:
    """Legacy compatibility."""
    parts = command.split()
    cleaned = [word for word in parts if word not in words]
    return " ".join(cleaned).strip()


def get_intent_confidence(intent: str, command: str) -> float:
    result = detect_intent(command)
    if result["intent"] == intent:
        return result["confidence"]
    if intent in result.get("all_intents", []):
        idx = result["all_intents"].index(intent)
        return max(0.3, result["confidence"] - 0.2 * (idx + 1))
    return 0.0