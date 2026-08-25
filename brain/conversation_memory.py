"""
ULTRON V3
Conversation Memory System
Thread-Safe & Atomic File Persistence
"""

import json
import os
import threading
from datetime import datetime
from core.logger import logger

CHAT_FILE = "data/conversation_history.json"
_chat_lock = threading.RLock()


def load_chat_history():
    with _chat_lock:
        if not os.path.exists(CHAT_FILE):
            return []

        try:
            with open(CHAT_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
        except json.JSONDecodeError as e:
            logger.warning(f"[ConversationMemory] File '{CHAT_FILE}' corrupted: {e}. Resetting history.")
            try:
                if os.path.exists(CHAT_FILE):
                    os.replace(CHAT_FILE, CHAT_FILE + ".corrupted")
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"[ConversationMemory] Load error: {e}")
            return []


def save_chat(user, assistant):
    with _chat_lock:
        history = load_chat_history()

        conversation = {
            "time": str(datetime.now()),
            "user": user,
            "assistant": assistant
        }

        history.append(conversation)
        history = history[-50:]

        try:
            os.makedirs("data", exist_ok=True)
            temp_file = CHAT_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(history, file, indent=4, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temp_file, CHAT_FILE)
            return True
        except Exception as e:
            logger.error(f"[ConversationMemory] Save error: {e}")
            temp_file = CHAT_FILE + ".tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return False


def get_recent_chats(limit=5):
    with _chat_lock:
        history = load_chat_history()
        return history[-limit:]