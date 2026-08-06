from brain.command_handler import handle_command


commands = [

    "ultron status",

    "what time is it",

    "battery level",

    "what is today's date"

]


for c in commands:

    print(
        "Command:",
        c
    )

    print(
        "ULTRON:",
        handle_command(c)
    )

    print("-"*30)