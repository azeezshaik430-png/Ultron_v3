"""
ULTRON V3
Smart Command Parser
"""


def clean_command(command):

    command = command.lower().strip()


    remove_words = [

        "please",
        "ultron",
        "can you",
        "could you",
        "my"

    ]


    for word in remove_words:

        command = command.replace(
            word,
            ""
        )


    return command.strip()



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