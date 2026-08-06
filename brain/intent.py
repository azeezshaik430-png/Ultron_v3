"""
ULTRON V3
Natural Language Intent Detection
"""


OPEN_WORDS = [
    "open",
    "launch",
    "start",
    "run",
    "execute"
]


CLOSE_WORDS = [
    "close",
    "exit",
    "quit",
    "shutdown"
]


def clean_target(command, words):

    for word in words:
        command = command.replace(word, "")

    return command.strip()



def detect_intent(command: str):

    command = command.lower().strip()


    for word in OPEN_WORDS:

        if word in command:

            return {
                "intent": "OPEN_APP",
                "target": clean_target(command, OPEN_WORDS)
            }



    for word in CLOSE_WORDS:

        if word in command:

            return {
                "intent": "CLOSE_APP",
                "target": clean_target(command, CLOSE_WORDS)
            }



    return {
        "intent": "CHAT",
        "target": command
    }