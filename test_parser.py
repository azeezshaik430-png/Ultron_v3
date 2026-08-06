from brain.smart_parser import detect_action


commands = [

    "open my browser",

    "please launch internet",

    "ultron go to sleep",

    "stop ultron",

    "close brave"

]


for c in commands:

    print(
        c,
        "=>",
        detect_action(c)
    )