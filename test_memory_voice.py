from brain.command_handler import handle_command


commands = [

    "remember my name is Azeez",

    "what is my name"

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