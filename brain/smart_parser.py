"""
ULTRON V3
Smart Command Parser
"""


def clean_command(command):
    command = command.lower().strip()

    protected_phrases = [
        "shutdown ultron", "exit ultron", "close ultron",
        "stop ultron", "quit ultron", "terminate ultron",
        "shutdown computer", "shutdown pc", "turn off computer",
        "turn off pc", "power off computer", "power off windows",
        "restart computer", "restart pc", "reboot computer", "reboot pc",
        "sign out", "log out windows", "lock computer", "lock pc",
        "factory reset", "system reset", "reset my computer",
        "reinstall windows", "restore factory settings",
        "format drive", "format disk", "format c drive", "format d drive",
        "delete all files", "delete files", "delete everything", "erase all files",
        "confirm reset", "confirm format", "confirm delete",
        "yes boss", "never mind"
    ]

    for phrase in protected_phrases:
        if phrase in command:
            return command

    remove_words = [
        "please",
        "can you",
        "could you",
        "my"
    ]

    for word in remove_words:
        command = command.replace(word, "")

    words = command.split()
    if "ultron" in words and len(words) > 1:
        words = [w for w in words if w != "ultron"]

    result = " ".join(words).strip()
    return result if result else command



def detect_action(command):

    command = clean_command(command)



    # OPEN

    if "open" in command or "start" in command or "launch" in command:

        return "OPEN"



    # CLOSE

    if "close" in command or "exit" in command:

        return "CLOSE"



    # SLEEP

    if "sleep" in command:

        return "SLEEP"



    # STOP

    if "stop" in command or "shutdown" in command:

        return "STOP"



    return "UNKNOWN"