"""
ULTRON V3
Command Handler v4.2

Smart Parser
Memory System
App Control
Windows Control
File Manager
System Control
Volume Control
AI Fallback

Author: Boss
"""


import webbrowser
import os
from brain.ollama_brain import ask_ollama

from brain.smart_parser import (
    detect_action,
    clean_command
)

from brain.memory import recall

from brain.smart_memory import (
    extract_memory
)


from skills.app_control import (
    open_app,
    close_app
)


from skills.search_files import (
    search_item
)


from skills.system_control import (
    get_time,
    get_date,
    get_battery,
    system_status
)


from skills.windows_control import (
    lock_pc,
    open_settings,
    shutdown_pc,
    restart_pc,
    sleep_pc
)


from skills.file_manager import (
    open_downloads,
    open_desktop,
    open_documents,
    open_d_drive,
    open_c_drive
)


from skills.volume_control import (
    volume_up,
    volume_down,
    mute,
    unmute,
    max_volume,
    min_volume
)



# ==================================
# MAIN COMMAND HANDLER
# ==================================

def handle_command(command):


    original = command.lower().strip()


    command = clean_command(original)



    if not command:
        return "Waiting Boss"



    # ==================================
    # SMART MEMORY
    # ==================================

    memory = extract_memory(original)

    if memory:
        return memory



    # ==================================
    # MEMORY CHECK
    # ==================================

    if (
        "what is my name" in command
        or "who am i" in command
    ):


        name = recall("name")


        if name:
            return f"Your name is {name}"


        return "I don't know your name yet"



    # ==================================
    # SYSTEM INFO
    # ==================================

    if "system status" in command or "status" in command:

        return system_status()



    if "battery" in command:

        return get_battery()



    if "time" in command:

        return get_time()



    if "date" in command:

        return get_date()



    # ==================================
    # FILE MANAGER
    # ==================================


    if "open downloads" in command:

        open_downloads()

        return "Opening downloads"



    if "open desktop" in command:

        open_desktop()

        return "Opening desktop"



    if "open documents" in command:

        open_documents()

        return "Opening documents"



    if "open d drive" in command:

        open_d_drive()

        return "Opening D drive"



    if "open c drive" in command:

        open_c_drive()

        return "Opening C drive"




    # ==================================
    # VOLUME CONTROL
    # ==================================


    if "volume up" in command:

        volume_up()

        return "Increasing volume"



    if "volume down" in command:

        volume_down()

        return "Decreasing volume"



    if "mute" in command:

        mute()

        return "Muting"



    if "unmute" in command:

        unmute()

        return "Unmuting"



    if "maximum volume" in command:

        max_volume()

        return "Maximum volume"



    if "minimum volume" in command:

        min_volume()

        return "Minimum volume"




    # ==================================
    # WINDOWS CONTROL
    # ==================================


    if "lock pc" in command:

        lock_pc()

        return "Locking PC"



    if "shutdown" in command:

        shutdown_pc()

        return "Shutting down"



    if "restart" in command:

        restart_pc()

        return "Restarting"



    if "sleep pc" in command:

        sleep_pc()

        return "Going to sleep mode"



    if "settings" in command:

        open_settings()

        return "Opening settings"




    # ==================================
    # OPEN / CLOSE APPS
    # ==================================


    action = detect_action(command)



    if action == "OPEN":


        target = (
            command
            .replace("open","")
            .strip()
        )


        if open_app(target):

            return f"Opening {target}"


        return f"I can't find {target}"




    if action == "CLOSE":


        target = (
            command
            .replace("close","")
            .strip()
        )


        close_app(target)


        return f"Closing {target}"





    # ==================================
    # SEARCH
    # ==================================


    if command.startswith("search"):


        query = (
            command
            .replace("search","")
            .strip()
        )


        search_item(query)


        return f"Searching {query}"





    # ==================================
    # WEBSITE
    # ==================================


    if "open youtube" in command:

        webbrowser.open(
            "https://youtube.com"
        )

        return "Opening YouTube"



    if "open google" in command:

        webbrowser.open(
            "https://google.com"
        )

        return "Opening Google"





    # ==================================
    # AI FALLBACK
    # ==================================

    return ask_ollama(command)






# ==================================
# AI BASIC RESPONSE
# ==================================

def chat_response(command):


    replies = {


        "hello":
        "Hello Boss, ULTRON is online",


        "hi":
        "Hi Boss",


        "who are you":
        "I am ULTRON V3 Personal AI Assistant",


        "top ultron":
        "ULTRON V3 system running successfully"

    }



    for key in replies:


        if key in command:

            return replies[key]



    return (
        "Sorry Boss, "
        "I don't understand this command yet"
    )