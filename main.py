"""
ULTRON V3 - Thin Entry Point
Entry Point & System Launcher with Graceful Shutdown Sequence
Version: 3.0
"""

import time
import logging
import sounddevice as sd
from core.config import config
from core.logger import logger
from core.session import session
from brain.orchestrator import orchestrator
from voice.wake_listener import wait_for_wake_word
from voice.speech_input import listen
from voice.speech_output import speak, stop_speaking


def start_ultron() -> None:
    """Bootstraps ULTRON core infrastructure and starts active loop."""
    logger.info("==================================================")
    logger.info(f"{config.ASSISTANT_NAME} V{config.VERSION} - Personal AI Assistant")
    logger.info("Core Systems ONLINE")
    logger.info("==================================================")

    # Clean runtime reset on every application startup
    session.reset()
    speak(f"Welcome back {config.OWNER_NAME}. {config.ASSISTANT_NAME} system is online.")

    try:
        while True:
            try:
                wait_for_wake_word()
                session.enter_active()

                while session.is_active_mode:
                    command = listen()
                    if not command:
                        continue

                    command_str = command.lower().strip()
                    if command_str in ["sleep", "go to sleep", "sleep ultron", "good night"]:
                        speak("Going to sleep Boss. Say Hey Ultron to wake me.")
                        session.enter_sleep()
                        break

                    if command_str in ["logout", "lock ultron"]:
                        session.set_auth(False)
                        stop_speaking()
                        session.enter_sleep()
                        break

                    from brain.orchestrator import is_ultron_shutdown
                    if is_ultron_shutdown(command_str, command_str) or command_str in ["exit", "quit"]:
                        speak("Goodbye Boss. Shutting down ULTRON.")
                        return

                    result = orchestrator.process_command(command_str)
                    logger.info(f"{config.ASSISTANT_NAME}: {result}")
                    if not session.session_data.pop("_already_spoken", False):
                        speak(result)
                    time.sleep(0.2)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt detected. Shutting down...")
                break
            except Exception as e:
                logger.error(f"ULTRON Core Loop Error: {e}")
    finally:
        # GRACEFUL SHUTDOWN SEQUENCE
        logger.info("Executing Graceful Shutdown Sequence...")
        # 1. Save session state
        session.save()
        # 2. Reset session authentication and state
        session.reset()
        # 3. Stop audio synthesis
        stop_speaking()
        # 4. Close microphone & audio streams
        try:
            sd.stop()
        except Exception:
            pass
        logger.info("ULTRON Session Cleanly Shutdown.")
        # 5. Flush and close logger handlers
        logging.shutdown()


if __name__ == "__main__":
    start_ultron()