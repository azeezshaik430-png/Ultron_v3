"""
ULTRON V3
Command Router
"""


def route(intent_data):

    intent = intent_data.get("intent")


    if intent == "OPEN_APP":
        return "APP_OPEN"


    if intent == "CLOSE_APP":
        return "APP_CLOSE"


    if intent == "CHAT":
        return "AI_CHAT"


    return "UNKNOWN"