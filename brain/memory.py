"""
ULTRON V3
Advanced Memory System v2.0

Safe JSON Handling & Atomic Persistence
Thread-Safe Key-Value & Semantic Sync
"""

import json
import os
import threading
from core.logger import logger

MEMORY_FILE = "data/memory.json"
_memory_lock = threading.RLock()


# ==================================
# LOAD MEMORY
# ==================================

def load_memory():
    with _memory_lock:
        try:
            if not os.path.exists(MEMORY_FILE):
                return {}

            with open(MEMORY_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}

        except json.JSONDecodeError as e:
            logger.warning(f"[Memory] File '{MEMORY_FILE}' corrupted: {e}. Creating backup and resetting.")
            try:
                if os.path.exists(MEMORY_FILE):
                    os.replace(MEMORY_FILE, MEMORY_FILE + ".corrupted")
            except Exception:
                pass
            return {}

        except Exception as e:
            logger.error(f"[Memory] Memory Load Error: {e}")
            return {}


# ==================================
# SAVE MEMORY (Atomic File Write)
# ==================================

def save_memory(data):
    with _memory_lock:
        try:
            os.makedirs("data", exist_ok=True)
            temp_file = MEMORY_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temp_file, MEMORY_FILE)
            return True

        except Exception as e:
            logger.error(f"[Memory] Memory Save Error: {e}")
            temp_file = MEMORY_FILE + ".tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return False


# ==================================
# REMEMBER (Canonical Path + Vector Sync)
# ==================================

def remember(key, value):
    with _memory_lock:
        memory = load_memory()
        memory[key] = value
        save_memory(memory)

        # Sync to SemanticMemoryStore for vector similarity retrieval
        try:
            from brain.semantic_memory import SemanticMemoryStore
            store = SemanticMemoryStore()
            store.store_memory(key, value)
        except Exception as err:
            logger.debug(f"[Memory] Semantic vector store auto-sync notice: {err}")

        # Emit MEMORY_UPDATED event over EventBus
        try:
            from core.event_bus import event_bus
            event_bus.publish("MEMORY_UPDATED", key=key, value=value, action="remember")
        except Exception:
            pass

        return f"I will remember that {key} is {value}"


# ==================================
# RECALL
# ==================================

def recall(key):
    with _memory_lock:
        memory = load_memory()
        return memory.get(key, None)


# ==================================
# CLEAR MEMORY
# ==================================

def clear_memory():
    with _memory_lock:
        save_memory({})
        try:
            from brain.semantic_memory import SemanticMemoryStore
            SemanticMemoryStore().clear()
        except Exception:
            pass
        return "All memories cleared Boss"