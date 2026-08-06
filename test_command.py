"""
ULTRON V3
Command System Test
"""

from brain.command_handler import handle_command


commands = [
    "open brave",
    "open browser",
    "launch internet",
    "start terminal",
    "open code editor"
]


print("Testing Ultron Command System...\n")


for command in commands:

    result = handle_command(command)

    print("Command:", command)
    print("Result:", result)
    print("-" * 30)