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
from voice.speech_input import listen, listen_confirmation
from voice.speech_output import speak, stop_speaking


def start_ultron() -> None:
    """Bootstraps ULTRON core infrastructure and starts active loop."""
    logger.info("==================================================")
    logger.info(f"{config.ASSISTANT_NAME} V{config.VERSION} - Personal AI Assistant")
    logger.info("Core Systems ONLINE")
    logger.info("==================================================")

    # Clean runtime reset on every application startup
    session.reset()
    
    # Preload VoiceEncoder neural model asynchronously in background daemon thread
    from voice.voice_guard import preload_voice_guard
    preload_voice_guard()

    speak(f"Welcome back {config.OWNER_NAME}. {config.ASSISTANT_NAME} system is online.")

    try:
        while True:
            try:
                wake_ok, initial_cmd = wait_for_wake_word()
                session.enter_active()

                first_turn = True
                while session.is_active_mode:
                    if first_turn and initial_cmd:
                        command = initial_cmd
                        first_turn = False
                    elif session.pending_confirmation:
                        first_turn = False
                        expires_at = session.pending_confirmation.get("expires_at", time.time() + 15.0)
                        command = listen_confirmation(expires_at=expires_at)
                        if not command:
                            if session.is_confirmation_expired(timeout_seconds=15.0):
                                result = orchestrator.process_command("")
                                logger.info(f"{config.ASSISTANT_NAME}: {result}")
                                if not session.session_data.pop("_already_spoken", False):
                                    speak(result)
                            continue
                    else:
                        first_turn = False
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
                        is_conf = session.pending_confirmation is not None
                        speak(result, allow_interruption=not is_conf)
                        if is_conf and session.pending_confirmation:
                            session.mark_confirmation_input_window_started()
                            now = time.time()
                            created_at = session.pending_confirmation.get("created_at", now)
                            start_at = session.pending_confirmation.get("input_window_started_at", now)
                            expires_at = session.pending_confirmation.get("expires_at", now + 15.0)
                            rem_ms = (expires_at - now) * 1000.0
                            logger.info(
                                f"[ConfirmationTiming] confirmation_created_at: {created_at:.4f} | "
                                f"confirmation_input_window_started: {start_at:.4f} | "
                                f"confirmation_expires_at: {expires_at:.4f} | "
                                f"remaining_confirmation_ms: {rem_ms:.2f} ms"
                            )

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