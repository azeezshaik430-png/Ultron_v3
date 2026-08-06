"""
ULTRON V3
Smart Memory Extractor V4

Advanced Personal Memory Detection
"""

from brain.memory import remember


def extract_memory(command):

    command = command.lower().strip()


    # NAME
    if "my name is" in command:

        value = command.split("my name is")[1].strip()

        if value:
            return remember("name", value)



    # LIKES

    if "i like" in command or "i love" in command:

        if "i like" in command:
            value = command.split("i like")[1].strip()

        else:
            value = command.split("i love")[1].strip()


        if value:
            return remember("likes", value)



    # FAVORITE GAME

    if "my favorite game is" in command or "my favourite game is" in command:

        value = command.replace(
            "my favourite game is",
            ""
        ).replace(
            "my favorite game is",
            ""
        ).strip()


        if value:
            return remember(
                "favorite_game",
                value
            )



    # FAVORITE MOVIE

    if (
        "my favorite movie is" in command
        or "my favourite movie is" in command
        or "my fav movie is" in command
    ):

        value = command.replace(
            "my favorite movie is",
            ""
        ).replace(
            "my favourite movie is",
            ""
        ).replace(
            "my fav movie is",
            ""
        ).strip()


        if value:
            return remember(
                "favorite_movie",
                value
            )



    # LAPTOP

    if "my laptop is" in command:

        value = command.split(
            "my laptop is"
        )[1].strip()


        if value:
            return remember(
                "laptop",
                value
            )



    # PHONE

    if "my phone is" in command:

        value = command.split(
            "my phone is"
        )[1].strip()


        if value:
            return remember(
                "phone",
                value
            )



    # PROJECT

    if "i am building" in command:

        value = command.split(
            "i am building"
        )[1].strip()


        if value:
            return remember(
                "project",
                value
            )



    # CUSTOM MEMORY

    if "remember that" in command:

        data = command.split(
            "remember that"
        )[1].strip()


        if " is " in data:

            key,value = data.split(
                " is ",
                1
            )


            return remember(
                key.strip(),
                value.strip()
            )


    return None