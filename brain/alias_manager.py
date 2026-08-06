"""
ULTRON V3
App Alias Manager
"""

import json


def load_aliases():

    with open("data/aliases.json", "r") as file:
        return json.load(file)



def resolve_alias(name):

    aliases = load_aliases()

    name = name.lower().strip()

    return aliases.get(name, name)