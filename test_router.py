from brain.router import route


tests = [
    {
        "intent": "OPEN_APP",
        "target": "brave"
    },
    {
        "intent": "CLOSE_APP",
        "target": "chrome"
    },
    {
        "intent": "CHAT",
        "target": "hello"
    }
]


for test in tests:

    result = route(test)

    print("Input:", test)
    print("Route:", result)
    print("-" * 30)