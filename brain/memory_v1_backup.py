"""
ULTRON V3
Memory System
"""

import json
import os


MEMORY_FILE = "data/memory.json"



def load_memory():

    if not os.path.exists(MEMORY_FILE):

        return {}


    with open(MEMORY_FILE, "r") as file:

        return json.load(file)



def save_memory(data):

    with open(MEMORY_FILE, "w") as file:

        json.dump(
            data,
            file,
            indent=4
        )



def remember(key, value):

    memory = load_memory()

    memory[key] = value

    save_memory(memory)


    return f"I will remember that {key} is {value}"



def recall(key):

    memory = load_memory()

    return memory.get(
        key,
        None
    )