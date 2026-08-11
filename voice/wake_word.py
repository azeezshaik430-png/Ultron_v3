"""
ULTRON V3
Wake Word System with Phonetic Variation & Combined Command Extraction
"""

import re
from typing import Tuple

# Recognized wake word root variations (phonetic & Whisper mis-transcriptions)
WAKE_VARIATIONS = [
    "ultron",
    "altron",
    "aultron",
    "alpron",
    "outron",
    "alltron",
    "oltron",
    "eltron",
    "ultro",
]

# Common wake word prefix phrases
WAKE_PREFIXES = [
    "hey",
    "hello",
    "hi",
    "ok",
    "okay",
    "you",
    "wake up",
    "please",
]


def check_wake_word(command: str) -> bool:
    """Return True if command contains any valid wake word variation."""
    has_wake, _ = extract_wake_word_and_command(command)
    return has_wake


def extract_wake_word_and_command(command: str) -> Tuple[bool, str]:
    """
    Check if transcript contains a wake word variation.
    If found, return (True, remaining_command_string).
    If not found, return (False, "").
    """
    if not command:
        return False, ""

    text = command.lower().strip()
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return False, ""

    wake_idx = -1
    for i, w in enumerate(words):
        if any(v in w for v in WAKE_VARIATIONS):
            wake_idx = i
            break

    if wake_idx == -1:
        return False, ""

    # Extract remaining command after the wake word
    remainder_words = words[wake_idx + 1:]
    
    # Strip any leading filler words from remainder (e.g. "please", "can you")
    while remainder_words and remainder_words[0] in ["please", "can", "you", "to", "and"]:
        remainder_words.pop(0)

    remaining_command = " ".join(remainder_words).strip()
    return True, remaining_command