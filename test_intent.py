from brain.intent import detect_intent


commands = [
    "open brave",
    "close chrome",
    "what is artificial intelligence"
]


for command in commands:

    result = detect_intent(command)

    print("Command:", command)
    print("Result:", result)
    print("-" * 30)