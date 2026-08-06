from brain.smart_memory import extract_memory


tests = [

    "my name is Azeez",

    "I like coding",

    "my favorite game is Palworld"

]


for t in tests:

    print(
        "Command:",
        t
    )

    print(
        extract_memory(t)
    )

    print("-"*30)