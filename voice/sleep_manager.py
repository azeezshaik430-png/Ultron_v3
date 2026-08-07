"""
ULTRON V3 - Sleep Manager
"""

from core.logger import logger
from core.session import session


class SleepManager:
    """Manages system sleep and active wake states."""

    def __init__(self) -> None:
        self.sleeping: bool = False

    def sleep(self) -> None:
        self.sleeping = True
        session.enter_sleep()
        logger.info("ULTRON: Entering sleep mode")

    def wake(self) -> None:
        self.sleeping = False
        session.enter_active()
        logger.info("ULTRON: Wake mode activated")

    def is_sleeping(self) -> bool:
        return self.sleeping