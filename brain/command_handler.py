"""
ULTRON V3
Command Handler
"""

from brain.intent import detect_intent
from brain.router import route
from skills.app_control import open_app


def handle_command(command):

    # Step 1: Understand command
    intent_data = detect_intent(command)


    # Step 2: Decide action
    destination = route(intent_data)


    # Step 3: Execute skill

    if destination == "APP_OPEN":

        result = open_app(intent_data["target"])

        return result


    if destination == "AI_CHAT":

        return "CHAT"


    if destination == "APP_CLOSE":

        return "CLOSE COMMAND"


    return "I don't understand"