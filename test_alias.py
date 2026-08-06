"""
ULTRON V3
Alias Test
"""

from brain.alias_manager import resolve_alias


tests = [
    "browser",
    "internet",
    "music",
    "code editor",
    "terminal"
]


print("Testing Alias System...\n")


for item in tests:

    result = resolve_alias(item)

    print(item, "=>", result)