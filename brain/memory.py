"""
ULTRON V3
Advanced Memory System v2.0

Safe JSON Handling
Persistent Memory
"""

import json
import os


MEMORY_FILE = "data/memory.json"



# ==================================
# LOAD MEMORY
# ==================================

def load_memory():

    try:

        if not os.path.exists(MEMORY_FILE):

            return {}


        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)



    except json.JSONDecodeError:

        print("Memory file corrupted. Resetting...")

        return {}



    except Exception as e:

        print(
            "Memory Load Error:",
            e
        )

        return {}




# ==================================
# SAVE MEMORY
# ==================================

def save_memory(data):

    try:

        os.makedirs(
            "data",
            exist_ok=True
        )


        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8"
        ) as file:


            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )


        return True



    except Exception as e:

        print(
            "Memory Save Error:",
            e
        )

        return False




# ==================================
# REMEMBER
# ==================================

def remember(key, value):


    memory = load_memory()


    memory[key] = value


    save_memory(memory)



    return (
        f"I will remember that "
        f"{key} is {value}"
    )




# ==================================
# RECALL
# ==================================

def recall(key):


    memory = load_memory()


    return memory.get(
        key,
        None
    )




# ==================================
# CLEAR MEMORY
# ==================================

def clear_memory():

    save_memory({})


    return "All memories cleared Boss"