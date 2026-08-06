from voice.wake_word import check_wake_word


tests = [
    "hey ultron",
    "hello ultron",
    "wake up ultron",
    "ultron wake up",
    "open brave"
]


for t in tests:

    print(
        t,
        "=>",
        check_wake_word(t)
    )