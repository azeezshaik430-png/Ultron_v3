"""
ULTRON V3
Smart Memory Extractor V2
"""

from brain.memory import remember


def extract_memory(command):

    command = command.lower().strip()


    # =========================
    # NAME
    # =========================

    if "my name is" in command:

        name = command.split("my name is")[1].strip()

        if name:
            return remember("name", name)



    # =========================
    # LIKES
    # =========================

    if "i like" in command:

        like = command.split("i like")[1].strip()

        if like:
            return remember("likes", like)



    # =========================
    # FAVORITE GAME
    # =========================

    if "my favorite game is" in command:

        game = command.split("my favorite game is")[1].strip()

        if game:
            return remember("favorite_game", game)



    # =========================
    # LAPTOP
    # =========================

    if "my laptop is" in command:

        laptop = command.split("my laptop is")[1].strip()

        if laptop:
            return remember("laptop", laptop)



    # =========================
    # PHONE
    # =========================

    if "my phone is" in command:

        phone = command.split("my phone is")[1].strip()

        if phone:
            return remember("phone", phone)



    # =========================
    # PROJECT
    # =========================

    if "i am building" in command:

        project = command.split("i am building")[1].strip()

        if project:
            return remember("project", project)



    return None