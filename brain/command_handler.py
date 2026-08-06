"""
ULTRON V3
Command Handler v4.4

Professional Edition

Features
---------
✔ Smart Memory
✔ Personal Memory
✔ App Control
✔ Windows Control
✔ File Manager
✔ Volume Control
✔ AI Fallback

Author: Boss
"""

import webbrowser

from brain.ollama_brain import ask_ollama

from brain.smart_parser import (
    detect_action,
    clean_command
)

from brain.memory import (
    recall,
    load_memory
)

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
    shutdown_pc,
    restart_pc,
    sleep_pc,
    open_settings
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


# ============================================
# MAIN COMMAND HANDLER
# ============================================

def handle_command(command):

    original = command.lower().strip()

    command = clean_command(original)

    if not command:
        return "Waiting Boss"


    # ====================================
    # SMART MEMORY
    # ====================================

    memory = extract_memory(original)

    if memory:
        return memory


    # ====================================
    # SHOW MEMORY
    # ====================================

    if (
        "show my memories" in command
        or "what do you remember about me" in command
    ):

        memories = load_memory()

        if not memories:
            return "I don't have any memories yet Boss"

        response = "Boss, I remember:\n"

        for key, value in memories.items():

            if key == "name":
                response += f"• Your name is {value}\n"

            elif key == "likes":
                response += f"• You like {value}\n"

            elif key == "favorite_game":
                response += f"• Favorite game: {value}\n"

            elif key == "laptop":
                response += f"• Laptop: {value}\n"

            elif key == "phone":
                response += f"• Phone: {value}\n"

            elif key == "project":
                response += f"• Current project: {value}\n"

        return response
        # ====================================
    # PERSONAL MEMORY
    # ====================================

    if "what is my name" in command or "who am i" in command:

        name = recall("name")

        if name:
            return f"Your name is {name}"

        return "I don't know your name yet Boss."


    if "what is my laptop" in command:

        laptop = recall("laptop")

        if laptop:
            return f"Your laptop is {laptop}"

        return "I don't know your laptop yet Boss."


    if "what is my phone" in command:

        phone = recall("phone")

        if phone:
            return f"Your phone is {phone}"

        return "I don't know your phone yet Boss."


    if "what is my project" in command:

        project = recall("project")

        if project:
            return f"You are building {project}"

        return "I don't know your project yet Boss."


    if "what do i like" in command:

        likes = recall("likes")

        if likes:
            return f"You like {likes}"

        return "I don't know your interests yet Boss."


    if "what is my favorite game" in command:

        game = recall("favorite_game")

        if game:
            return f"Your favorite game is {game}"

        return "I don't know your favorite game yet Boss."


    # ====================================
    # SYSTEM
    # ====================================

    if "system status" in command or command == "status":
        return system_status()

    if "battery" in command:
        return get_battery()

    if "time" in command:
        return get_time()

    if "date" in command:
        return get_date()


    # ====================================
    # FILE MANAGER
    # ====================================

    if "open downloads" in command:
        open_downloads()
        return "Opening Downloads"

    if "open desktop" in command:
        open_desktop()
        return "Opening Desktop"

    if "open documents" in command:
        open_documents()
        return "Opening Documents"

    if "open d drive" in command:
        open_d_drive()
        return "Opening D Drive"

    if "open c drive" in command:
        open_c_drive()
        return "Opening C Drive"


    # ====================================
    # VOLUME
    # ====================================

    if "volume up" in command:
        volume_up()
        return "Increasing volume"

    if "volume down" in command:
        volume_down()
        return "Decreasing volume"

    if "mute" in command:
        mute()
        return "Muted"

    if "unmute" in command:
        unmute()
        return "Unmuted"

    if "maximum volume" in command:
        max_volume()
        return "Volume set to maximum"

    if "minimum volume" in command:
        min_volume()
        return "Volume set to minimum"
        # ====================================
    # WINDOWS CONTROL
    # ====================================

    if "lock pc" in command:
        lock_pc()
        return "Locking your PC"

    if "shutdown" in command:
        shutdown_pc()
        return "Shutting down your PC"

    if "restart" in command:
        restart_pc()
        return "Restarting your PC"

    if "sleep pc" in command:
        sleep_pc()
        return "Putting your PC to sleep"

    if "settings" in command:
        open_settings()
        return "Opening Settings"


    # ====================================
    # OPEN / CLOSE APPS
    # ====================================

    action = detect_action(command)

    if action == "OPEN":

        target = command.replace("open", "").strip()

        if open_app(target):
            return f"Opening {target}"

        return f"I couldn't find {target}"


    if action == "CLOSE":

        target = command.replace("close", "").strip()

        close_app(target)

        return f"Closing {target}"


    # ====================================
    # SEARCH
    # ====================================

    if command.startswith("search"):

        query = command.replace(
            "search",
            ""
        ).strip()

        search_item(query)

        return f"Searching for {query}"


    # ====================================
    # WEBSITES
    # ====================================

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


    # ====================================
    # BASIC CHAT
    # ====================================

    basic = chat_response(command)

    if basic is not None:
        return basic


    # ====================================
    # AI FALLBACK
    # ====================================

    return ask_ollama(command)



# ============================================
# BASIC CHAT RESPONSES
# ============================================

def chat_response(command):

    replies = {

        "hello":
        "Hello Boss! ULTRON is online.",

        "hi":
        "Hi Boss!",

        "hey":
        "Hello Boss!",

        "good morning":
        "Good morning Boss!",

        "good night":
        "Good night Boss.",

        "thank you":
        "You're welcome Boss.",

        "thanks":
        "You're welcome Boss.",

        "who are you":
        "I am ULTRON V3, your personal AI assistant.",

        "how are you":
        "I'm fully operational Boss.",

        "top ultron":
        "ULTRON V3 is running successfully."
    }

    for key, value in replies.items():

        if key in command:
            return value

    return None