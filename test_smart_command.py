from brain.command_handler import handle_command


commands = [

    "please open my browser",

    "launch terminal",

    "ultron stop now"

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