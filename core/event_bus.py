"""
ULTRON V3 - Synchronous Event Bus
Enables decoupled component communication via simple pub/sub events.
"""

from typing import Callable, Dict, List, Any
from core.logger import logger


class EventBus:
    """Lightweight synchronous Event Bus."""

    # Event Constants
    VOICE_STARTED = "VOICE_STARTED"
    VOICE_STOPPED = "VOICE_STOPPED"
    MEMORY_UPDATED = "MEMORY_UPDATED"
    TASK_STARTED = "TASK_STARTED"
    TASK_FINISHED = "TASK_FINISHED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    MODEL_SWITCHED = "MODEL_SWITCHED"
    SYSTEM_READY = "SYSTEM_READY"

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[..., None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[..., None]) -> None:
        """Register a callback for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed {callback.__name__} to event '{event_type}'")

    def unsubscribe(self, event_type: str, callback: Callable[..., None]) -> None:
        """Unregister a callback for an event type."""
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed {callback.__name__} from event '{event_type}'")

    def publish(self, event_type: str, **kwargs: Any) -> None:
        """Synchronously publish an event to all registered subscribers."""
        logger.debug(f"Event published: '{event_type}' with payload {kwargs}")
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(**kwargs)
                except Exception as e:
                    logger.error(f"Error executing callback '{callback.__name__}' for event '{event_type}': {e}")


# Global Event Bus Singleton
event_bus = EventBus()
