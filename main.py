"""
ULTRON V3
Personal AI Assistant Core

Conversation Mode V1
Smart Memory + Sleep Mode + Wake Word + Voice Authentication

Author: Boss
Version: 4.0
"""


from voice.speech_input import listen

from voice.speech_output import (
    speak,
    speaking,
    stop_speaking
)

from voice.wake_listener import (
    wait_for_wake_word
)


from brain.command_handler import (
    handle_command
)

from brain.memory import (
    recall
)


import time



# =====================================
# ACTIVE CONVERSATION MODE
# =====================================

def active_mode():


    print(
        "ACTIVE MODE STARTED"
    )


    while True:


        command = listen()



        if not command:

            continue



        command = command.lower().strip()



        print(
            "\nCommand:",
            command
        )



        # ==============================
        # SLEEP COMMAND
        # ==============================


        if command in [

            "sleep ultron",
            "go to sleep",
            "ultron sleep",
            "sleep",
            "good night ultron"

        ]:


            speak(
                "Going to sleep Boss. Say Hey Ultron to wake me."
            )


            return "SLEEP"




        # ==============================
        # EXIT COMMAND
        # ==============================


        if command in [

            "exit",
            "quit",
            "shutdown ultron",
            "bye ultron",
            "turn off ultron"

        ]:


            speak(
                "Goodbye Boss. Shutting down."
            )


            return "EXIT"




        # ==============================
        # NORMAL COMMAND
        # ==============================


        result = handle_command(
            command
        )


        print(
            "ULTRON:",
            result
        )


        speak(
            result
        )


        time.sleep(0.2)
        # =====================================
# SLEEP MODE
# =====================================

def sleep_mode():


    print(
        "ULTRON sleeping... Waiting for wake word 😴"
    )


    verified = wait_for_wake_word()



    if verified:


        print("VOICE VERIFIED - ENTERING ACTIVE MODE")
        


        return True



    return False





# =====================================
# ULTRON START
# =====================================

def start_ultron():


    print("=" * 50)

    print(
        "ULTRON V3"
    )

    print(
        "Personal AI Assistant"
    )

    print(
        "Voice Input: ONLINE 🎤"
    )

    print(
        "Voice Output: ONLINE 🔊"
    )

    print(
        "Wake Word: ONLINE 🟢"
    )

    print(
        "Voice Authentication: ONLINE 🔐"
    )

    print(
        "Conversation Mode: ONLINE 💬"
    )

    print(
        "Memory System: ONLINE 🧠"
    )

    print(
        "System Ready 🚀"
    )

    print("=" * 50)



    # ==============================
    # MEMORY GREETING
    # ==============================


    name = recall(
        "name"
    )



    if name:


        speak(
            f"Welcome back {name}. Ultron system is online."
        )


    else:


        speak(
            "Hello Boss. Ultron system is online."
        )



    time.sleep(1)




    # ==============================
    # MAIN LOOP
    # ==============================


    while True:



        # Wait for wake word

        sleep_mode()



        # Enter conversation mode

        status = active_mode()




        if status == "SLEEP":


            continue




        if status == "EXIT":


            print(
                "ULTRON stopped"
            )


            break





# =====================================
# RUN
# =====================================

if __name__ == "__main__":


    start_ultron()