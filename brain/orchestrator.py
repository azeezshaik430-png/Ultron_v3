"""
ULTRON V3 - Central Brain Orchestrator
The single brain controller of ULTRON V3.
All user inputs flow strictly through Orchestrator -> Intent -> Planner -> Router -> Skills/LLM.
"""

import time
import webbrowser
from typing import Optional, Dict, Any

from core.logger import logger
from core.session import session
from core.event_bus import event_bus
from brain.llm_manager import llm_manager
from brain.smart_parser import detect_action, clean_command
from brain.memory import recall, load_memory
from brain.smart_memory import extract_memory
from brain.planner import plan
from brain.router import route, router_dispatcher
from voice.speech_output import stop_speaking

from skills.app_control import open_app, close_app
from skills.search_files import search_item
from skills.system_control import get_time, get_date, get_battery, system_status
from skills.windows_control import (
    lock_pc,
    shutdown_pc,
    restart_pc,
    sleep_pc,
    open_settings,
)
from skills.file_manager import (
    open_downloads,
    open_desktop,
    open_documents,
    open_d_drive,
    open_c_drive,
)
from skills.volume_control import (
    volume_up,
    volume_down,
    mute,
    unmute,
    max_volume,
    min_volume,
)


class Orchestrator:
    """Central Brain Orchestrator Controller."""

    def process_command(self, original_command: str) -> str:
        """
        Master input execution pipeline:
        Input -> Security/Memory -> Skill / Intent / Router -> LLM Fallback -> Response
        """
        if not original_command:
            return "Waiting Boss"

        original = original_command.lower().strip()
        command = clean_command(original)

        if not command and not original:
            return "Waiting Boss"

        logger.info(f"Processing Command: '{original}' (cleaned: '{command}')")
        event_bus.publish(event_bus.TASK_STARTED, command=original)

        # 0. SECURITY RESET & LOGOUT COMMANDS (REQUIREMENT 2)
        if command in ["logout", "lock ultron"] or original in ["logout", "lock ultron"]:
            logger.info("Executing Security Logout & Sleep Sequence...")
            session.set_auth(False)
            stop_speaking()
            session.enter_sleep()
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return "ULTRON locked Boss. Session logged out."

        if any(kw in original or kw in command for kw in ["verify me", "authenticate me", "reverify me", "security check"]):
            logger.info("Explicit Voice Re-verification Requested...")
            from voice.wake_listener import record_auth_voice
            from voice.voice_guard import verify_boss
            session.set_auth(False)
            voice_file = record_auth_voice()
            if verify_boss(voice_file):
                session.set_auth(True)
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                return "Voice Verified Boss. Session authenticated."
            else:
                session.enter_sleep()
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                return "Voice verification failed. Entering sleep mode."

        # 1. SMART MEMORY EXTRACTION
        memory_result = extract_memory(original)
        if memory_result:
            event_bus.publish(event_bus.MEMORY_UPDATED, result=memory_result)
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return memory_result

        # 2. PERSONAL MEMORY QUERIES (MUST NEVER CALL LLM)
        query_text = f"{original} {command}"

        if (
            "show my memories" in query_text
            or "what do you remember" in query_text
            or "my memories" in query_text
            or "remember about me" in query_text
        ):
            memories = load_memory()
            if not memories:
                res = "I don't have any memories yet Boss"
            else:
                res = "Boss, I remember:\n"
                for key, value in memories.items():
                    if key == "name":
                        res += f"• Your name is {value}\n"
                    elif key == "likes":
                        res += f"• You like {value}\n"
                    elif key == "favorite_game":
                        res += f"• Favorite game: {value}\n"
                    elif key == "laptop":
                        res += f"• Laptop: {value}\n"
                    elif key == "phone":
                        res += f"• Phone: {value}\n"
                    elif key == "project":
                        res += f"• Current project: {value}\n"
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if "name" in query_text and ("what" in query_text or "who" in query_text or "my" in query_text):
            name = recall("name")
            res = f"Your name is {name}" if name else "I don't know your name yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if "laptop" in query_text and ("what" in query_text or "my" in query_text):
            laptop = recall("laptop")
            res = f"Your laptop is {laptop}" if laptop else "I don't know your laptop yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if "phone" in query_text and ("what" in query_text or "my" in query_text):
            phone = recall("phone")
            res = f"Your phone is {phone}" if phone else "I don't know your phone yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if "project" in query_text and ("what" in query_text or "building" in query_text or "my" in query_text):
            project = recall("project")
            res = f"You are building {project}" if project else "I don't know your project yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if ("like" in query_text or "love" in query_text or "interests" in query_text) and ("what" in query_text or "my" in query_text):
            likes = recall("likes")
            res = f"You like {likes}" if likes else "I don't know your interests yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if ("favorite game" in query_text or "favourite game" in query_text or "fav game" in query_text):
            game = recall("favorite_game")
            res = f"Your favorite game is {game}" if game else "I don't know your favorite game yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        if ("favorite movie" in query_text or "favourite movie" in query_text or "fav movie" in query_text):
            movie = recall("favorite_movie")
            res = f"Your favorite movie is {movie}" if movie else "I don't know your favorite movie yet Boss."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        # 3. SYSTEM & DIAGNOSTICS
        if "system status" in command or command == "status":
            return system_status()
        if "battery" in command:
            return get_battery()
        if "time" in command:
            return get_time()
        if "date" in command:
            return get_date()

        # 4. FILE MANAGER
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

        # 5. VOLUME CONTROL
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

        # 6. WINDOWS OS CONTROL
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

        # 7. OPEN / CLOSE APPS
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

        # 8. SEARCH & WEBSITES
        if command.startswith("search"):
            query = command.replace("search", "").strip()
            search_item(query)
            return f"Searching for {query}"

        if "open youtube" in command:
            webbrowser.open("https://youtube.com")
            return "Opening YouTube"

        if "open google" in command:
            webbrowser.open("https://google.com")
            return "Opening Google"

        # 9. BASIC CHAT RESPONSES
        basic_chat = self._chat_response(command)
        if basic_chat is not None:
            return basic_chat

        # 10. UNIFIED LLM MANAGER FALLBACK
        result = llm_manager.ask(command)
        event_bus.publish(event_bus.TASK_FINISHED, command=command)
        return result

    def _chat_response(self, command: str) -> Optional[str]:
        """Predefined fast responses."""
        replies = {
            "hello": "Hello Boss! ULTRON is online.",
            "hi": "Hi Boss!",
            "hey": "Hello Boss!",
            "good morning": "Good morning Boss!",
            "good night": "Good night Boss.",
            "thank you": "You're welcome Boss.",
            "thanks": "You're welcome Boss.",
            "who are you": "I am ULTRON V3, your personal AI assistant.",
            "how are you": "I'm fully operational Boss.",
            "top ultron": "ULTRON V3 is running successfully.",
        }
        for key, value in replies.items():
            if key in command:
                return value
        return None


# Global Orchestrator Singleton
orchestrator = Orchestrator()
