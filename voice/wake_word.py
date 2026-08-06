"""
ULTRON V3
Wake Word System
"""


WAKE_WORDS = [

    "hey ultron",
    "hello ultron",
    "wake up ultron",
    "ultron wake up"

]


def check_wake_word(command):

    command = command.lower().strip()


    for word in WAKE_WORDS:

        if word in command:

            return True


    return False