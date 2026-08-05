from brain.command_handler import handle_command


print("Testing Ultron Command System...\n")


commands = [
    "open brave"
]


for command in commands:

    print("Command:", command)

    result = handle_command(command)

    print("Result:", result)

    print("-" * 30)