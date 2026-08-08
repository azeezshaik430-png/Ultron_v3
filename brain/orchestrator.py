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
from brain.smart_parser import detect_action, clean_command, detect_language_intent
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


import datetime
import os
import time
from core.config import config
from skills.windows_control import (
    lock_pc,
    shutdown_pc,
    restart_pc,
    sign_out_pc,
    sleep_pc,
    open_settings,
)

# Factory Reset, Format Drive, and Delete All Files are permanently unsupported for security.
PERMANENTLY_UNSUPPORTED_PHRASES = [
    "factory reset",
    "reset my computer",
    "reinstall windows",
    "restore factory settings",
    "system reset",
    "format drive",
    "format disk",
    "format c drive",
    "format d drive",
    "delete all files",
    "delete files",
    "delete everything",
    "erase all files",
]

ULTRON_SHUTDOWN_PHRASES = {
    "shutdown ultron",
    "exit ultron",
    "close ultron",
    "stop ultron",
    "quit ultron",
    "terminate ultron",
}

CONFIRM_RESPONSES = {"yes", "yes boss", "confirm", "continue", "proceed", "do it"}
CANCEL_RESPONSES = {"no", "cancel", "stop", "never mind"}

DANGEROUS_COMMANDS = {
    # Action key: (display_name, requires_double, action_phrase, exec_func)
    "shutdown pc": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),
    "shutdown computer": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),
    "turn off pc": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),
    "turn off computer": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),
    "power off computer": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),
    "power off windows": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),

    "restart pc": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "restart computer": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "reboot pc": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "reboot computer": ("Restart PC", False, "CONFIRM RESTART", restart_pc),

    "sign out": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),
    "log out windows": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),

    "lock pc": ("Lock PC", False, "CONFIRM LOCK", lock_pc),
    "lock computer": ("Lock PC", False, "CONFIRM LOCK", lock_pc),
}


def log_security_audit(command_name: str, result_status: str) -> None:
    """
    Log dangerous command audit entry strictly to logs/security.log.
    Only stores: timestamp, command, result.
    NEVER stores voice recordings, authentication state, confirmation payload, or personal memory.
    """
    try:
        log_dir = config.LOGS_DIR
        os.makedirs(log_dir, exist_ok=True)
        sec_log_path = os.path.join(log_dir, "security.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] Command: '{command_name}' | Status: '{result_status}'\n"
        with open(sec_log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        logger.info(f"Security Audit Logged: {command_name} -> {result_status}")
    except Exception as e:
        logger.error(f"Failed to write security audit log: {e}")


def is_ultron_shutdown(command_raw: str, command_clean: str) -> bool:
    raw = command_raw.lower().strip()
    clean = command_clean.lower().strip()
    if raw in ULTRON_SHUTDOWN_PHRASES or clean in ULTRON_SHUTDOWN_PHRASES:
        return True
    for phrase in ULTRON_SHUTDOWN_PHRASES:
        if phrase in raw or phrase in clean:
            return True
    return False


class Orchestrator:
    """Central Brain Orchestrator Controller."""

    def __init__(self, bus: Optional[Any] = None, agent_manager: Optional[Any] = None) -> None:
        from brain.agent_bus import AgentMemoryBus
        from brain.agent_manager import AgentManager
        from agents.system_agent import SystemAgent
        from agents.memory_agent import MemoryAgent
        from agents.background_task_agent import BackgroundTaskAgent
        from agents.planning_agent import PlanningAgent
        from agents.research_agent import ResearchAgent
        from agents.coding_agent import CodingAgent

        from agents.vision_agent import VisionAgent
        from agents.browser_agent import BrowserAgent

        self.bus = bus or AgentMemoryBus()
        if not getattr(self.bus, "_is_initialized", False):
            try:
                self.bus.initialize()
            except Exception as err:
                logger.debug(f"[Orchestrator] Bus initialize notice: {err}")

        self.agent_manager = agent_manager or AgentManager(bus=self.bus)
        if not getattr(self.agent_manager, "_is_initialized", False):
            try:
                self.agent_manager.initialize()
            except Exception as err:
                logger.debug(f"[Orchestrator] AgentManager initialize notice: {err}")

        # Instantiate & register all 8 domain agents
        self._system_agent = SystemAgent(bus=self.bus)
        self._memory_agent = MemoryAgent(bus=self.bus)
        self._background_agent = BackgroundTaskAgent(bus=self.bus)
        self._planning_agent = PlanningAgent(bus=self.bus)
        self._research_agent = ResearchAgent(bus=self.bus)
        self._coding_agent = CodingAgent(bus=self.bus)
        self._vision_agent = VisionAgent(bus=self.bus)
        self._browser_agent = BrowserAgent(bus=self.bus)

        for agent in [
            self._system_agent,
            self._memory_agent,
            self._background_agent,
            self._planning_agent,
            self._research_agent,
            self._coding_agent,
            self._vision_agent,
            self._browser_agent,
        ]:
            try:
                self.agent_manager.register_agent(agent)
            except Exception as err:
                logger.debug(f"[Orchestrator] Agent registration notice for '{agent.agent_id}': {err}")

    def shutdown(self) -> None:
        """Shutdown managed agents and bus cleanly."""
        try:
            if hasattr(self, "agent_manager") and self.agent_manager:
                self.agent_manager.shutdown()
        except Exception:
            pass
        try:
            if hasattr(self, "bus") and self.bus:
                self.bus.shutdown()
        except Exception:
            pass

    def _dispatch_to_domain_agent(self, command: str, original: str) -> Optional[str]:
        """Dispatch user request to appropriate registered domain agent if intent matches."""
        cmd = command.lower().strip()
        orig = original.lower().strip()
        t_id = f"task_{int(time.time() * 1000)}"

        # 1. Research Agent Intent
        if cmd.startswith("research ") or orig.startswith("research ") or "conduct research on" in cmd or "investigate topic" in cmd:
            query = cmd.replace("research", "").replace("conduct research on", "").replace("investigate topic", "").strip()
            res = self.agent_manager.dispatch_task("research_agent", t_id, {
                "action": "conduct_research",
                "query": query or orig,
            })
            if res.get("status") == "SUCCESS":
                summary = res.get("result", {}).get("synthesis", {}).get("summary", "")
                if summary:
                    return f"Research complete Boss: {summary}"
                return f"Research completed for query: {query}"
            elif res.get("status") == "ERROR":
                return f"Research task notice: {res.get('error')}"

        # 2. Coding Agent Intent
        if cmd.startswith("coding ") or "inspect repo" in cmd or "generate python code" in cmd or "run authorized tests" in cmd:
            action = "understand_repo_structure"
            if "generate python code" in cmd:
                action = "generate_code"
            elif "run authorized tests" in cmd:
                action = "run_authorized_tests"
            res = self.agent_manager.dispatch_task("coding_agent", t_id, {
                "action": action,
                "specification": cmd,
                "root_path": os.getcwd(),
            })
            if res.get("status") == "SUCCESS":
                return f"Coding Agent operation completed successfully."
            elif res.get("status") == "ERROR":
                return f"Coding Agent notice: {res.get('error')}"

        # 3. Planning Agent Intent
        if "create execution plan" in cmd or "build plan for" in cmd or cmd.startswith("plan "):
            obj = cmd.replace("create execution plan", "").replace("build plan for", "").replace("plan", "").strip()
            res = self.agent_manager.dispatch_task("planning_agent", t_id, {
                "action": "create_execution_plan",
                "objective": obj or orig,
            })
            if res.get("status") == "SUCCESS":
                p_id = res.get("result", {}).get("plan_id", "")
                steps = len(res.get("result", {}).get("steps", []))
                return f"Plan '{p_id}' created with {steps} execution steps Boss."

        # 4. Background Task Agent Intent
        if "submit background task" in cmd or "run async job" in cmd:
            res = self.agent_manager.dispatch_task("background_task_agent", t_id, {
                "action": "submit_task",
                "task_name": "AsyncJob",
                "payload": {"command": orig},
            })
            if res.get("status") == "SUCCESS":
                bg_id = res.get("result", {}).get("task_id", "")
                return f"Background task '{bg_id}' submitted successfully Boss."

        # 5. System & Storage Agent Intent
        storage_triggers = ["d drive", "c drive", "tell about d drive", "tell about c drive", "disk status", "storage status", "d: drive", "c: drive", "my storage", "my disk"]
        if any(k in cmd for k in storage_triggers):
            target_drive = "D" if ("d drive" in cmd or "d:" in cmd or "d_drive" in cmd) else ("C" if ("c drive" in cmd or "c:" in cmd) else None)
            res = self.agent_manager.dispatch_task("system_agent", t_id, {
                "action": "disk_info",
                "drive": target_drive,
            })
            if res.get("status") == "SUCCESS":
                return res.get("result", "")

        sys_info_triggers = [
            "tell my system", "tell me my system", "what is my system", "tell system", "my system",
            "system details", "system info", "system information", "system specs", "system specifications",
            "hardware info", "hardware details", "my hardware", "tell me my hardware",
            "cpu and ram", "my cpu", "my gpu", "tell me my cpu", "tell me my gpu",
            "pc specs", "computer specs", "computer specifications", "my computer details", "specs"
        ]
        if any(k in cmd for k in sys_info_triggers) or (("system" in cmd or "hardware" in cmd or "specs" in cmd) and any(w in cmd for w in ["tell", "what", "my", "info", "details", "get"])):
            res = self.agent_manager.dispatch_task("system_agent", t_id, {
                "action": "system_info",
            })
            if res.get("status") == "SUCCESS":
                return res.get("result", "")

        if "agent status" in cmd or "check agent health" in cmd or "system diagnostics" in cmd:
            res = self.agent_manager.dispatch_task("system_agent", t_id, {
                "action": "system_status",
            })
            if res.get("status") == "SUCCESS":
                agents_count = len(self.agent_manager.list_agents())
                return f"All {agents_count} domain agents are healthy and operational."

        # 6. Vision Agent Intent
        analyze_triggers = [
            "look at my screen", "what is on my screen", "what's on my screen", 
            "read my screen", "read the screen", "analyse my screen", "analyze my screen", 
            "analyse screen", "analyze screen", "analyse the screen", "analyze the screen", 
            "describe my screen", "describe what is on my screen", "inspect my screen", 
            "inspect the screen", "check my screen", "check the screen", "analyse this screen", 
            "analyze this screen", "analyse my display", "analyze my display",
            "screen meeda em undi"
        ]
        camera_triggers = ["camera capture", "take a picture", "capture camera"]
        screenshot_triggers = ["take a screenshot", "capture screen", "screenshot"]
        
        v_action = None
        if any(k in cmd or k in orig for k in analyze_triggers):
            v_action = "analyze_screen"
        elif any(k in cmd or k in orig for k in camera_triggers):
            v_action = "capture_camera"
        elif any(k in cmd or k in orig for k in screenshot_triggers):
            v_action = "capture_screen"
            
        if v_action:
            res = self.agent_manager.dispatch_task("vision_agent", t_id, {
                "action": v_action,
            })
            if res.get("status") == "SUCCESS":
                inner = res.get("result", {})
                raw_text = inner.get("result", "") if isinstance(inner, dict) else str(inner)
                if v_action in ["analyze_screen", "ocr"]:
                    from brain.llm_manager import llm_manager
                    prompt = f"Boss asked you to analyze/read their screen. Based on this raw screen data, provide a concise, natural language response describing what's on the screen. Do not mention 'Extracted Screen Content' or OCR garbage. Raw data:\n{raw_text}"
                    if getattr(session, "preferred_language", "en") == "te":
                        prompt += "\n\nCRITICAL INSTRUCTION: You MUST reply in natural conversational Telugu script! Explain what is on the screen in Telugu."
                    summary = llm_manager.ask(prompt)
                    logger.info("[VisionAgent] User-facing screen summary generated")
                    return summary
                return raw_text
            elif res.get("reason"):
                return f"Vision notice: {res.get('reason')}"

        # 7. Browser Agent Intent
        KNOWN_WEBSITES = {
            "youtube": "https://www.youtube.com",
            "whatsapp": "https://web.whatsapp.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "github": "https://github.com",
            "instagram": "https://www.instagram.com",
            "facebook": "https://www.facebook.com",
            "twitter": "https://twitter.com",
            "x": "https://x.com",
            "linkedin": "https://www.linkedin.com",
            "chatgpt": "https://chatgpt.com",
            "google ai studio": "https://aistudio.google.com",
        }
        
        browser_triggers = [
            "open ", "go to ", "navigate to ", "visit ", "search for ",
            "read ", "inspect ", "close "
        ]
        browser_suffixes = ["open cheyyi", "close cheyyi", "open chey", "close chey", "open cheyyandi", "close cheyyandi"]
        
        is_browser_command = False
        target_url = orig
        b_action = "open_url"
        
        if cmd.startswith("open http") or ("open" in cmd and any(ext in cmd for ext in [".com", ".org", ".net", ".io"])):
            is_browser_command = True
        elif any(orig.startswith(k) for k in browser_triggers) or any(orig.endswith(s) for s in browser_suffixes):
            # Strip prefixes
            for strip_term in browser_triggers:
                if target_url.startswith(strip_term):
                    target_url = target_url[len(strip_term):].strip()
                    break
            # Strip suffixes for mixed Telugu
            for strip_suffix in browser_suffixes:
                if target_url.endswith(strip_suffix):
                    target_url = target_url[:-len(strip_suffix)].strip()
                    break
            
            if target_url in KNOWN_WEBSITES:
                is_browser_command = True
                target_url = KNOWN_WEBSITES[target_url]
            elif target_url in ["browser", "tab", "page", "website"]:
                is_browser_command = True
                target_url = "" # Action applies to current browser
            elif "." in target_url and not " " in target_url:
                is_browser_command = True
                target_url = "https://" + target_url if not target_url.startswith("http") else target_url
            elif "search for " in orig:
                is_browser_command = True
                query = orig.split("search for ")[-1].strip().replace(" ", "+")
                target_url = f"https://www.google.com/search?q={query}"
        
        if is_browser_command:
            logger.info("[Orchestrator] Browser intent detected")
            if "close" in orig:
                logger.info("[Orchestrator] Browser close intent detected")
                b_action = "close_browser"
            elif "read " in orig or "inspect " in orig:
                b_action = "inspect_page"
                
            res = self.agent_manager.dispatch_task("browser_agent", t_id, {
                "action": b_action,
                "url": target_url or "https://example.com",
            })
            
            if res.get("status") == "SUCCESS":
                inner = res.get("result", {})
                
                # Check actual inner status returned by BrowserAgent
                inner_status = inner.get("status")
                res_msg = inner.get("result", "") if isinstance(inner, dict) else str(inner)
                reason = inner.get("reason", "") if isinstance(inner, dict) else ""
                
                if inner_status == "ERROR":
                    return f"I couldn't complete the browser action because {reason}"
                    
                if b_action == "open_url":
                    logger.info("[BrowserAgent] Navigation successful")
                    return f"{inner.get('title', target_url)} is open, Boss."
                elif b_action == "close_browser":
                    return "The browser has been closed."
                return res_msg
            elif res.get("reason"):
                return f"Browser notice: {res.get('reason')}"

        return None

    def process_command(self, original_command: str) -> str:
        """
        Master input execution pipeline:
        Input -> Security/Memory -> Domain Agent / Skill / Intent -> LLM Fallback -> Response
        """
        if not original_command:
            return "Waiting Boss"

        original = original_command.lower().strip()
        command = clean_command(original)

        if not command and not original:
            return "Waiting Boss"

        logger.info(f"Processing Command: '{original}' (cleaned: '{command}')")
        
        # Determine language context for this command
        input_lang, explicit_switch = detect_language_intent(original)
        if explicit_switch:
            session.preferred_language = explicit_switch
            event_bus.publish(event_bus.TASK_STARTED, command=original)
            res = "సరే బాస్. ఇక నుంచి తెలుగులో మాట్లాడతాను." if explicit_switch == "te" else "Sure, Boss. I'll speak in English from now on."
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return res

        current_lang = getattr(session, "preferred_language", "en") if not explicit_switch else explicit_switch
        
        event_bus.publish(event_bus.TASK_STARTED, command=original)

        def _format_local_response(english_response: str) -> str:
            """Translates deterministic outputs to Telugu internally."""
            if current_lang != "te":
                return english_response
            # Local mapping for fast Telugu responses without LLM latency
            mapping = {
                "YouTube is open, Boss.": "YouTube ఓపెన్ చేశాను, Boss.",
                "WhatsApp Web is open, Boss.": "WhatsApp ఓపెన్ చేశాను, Boss.",
                "The browser has been closed.": "Browser క్లోజ్ చేశాను, Boss.",
                "Switched to English mode.": "Sure Boss, I will speak in English.",
                "Voice Verified Boss. Session authenticated.": "మీ వాయిస్ వెరిఫై అయింది బాస్.",
                "Goodbye Boss. Shutting down ULTRON.": "గుడ్ బై బాస్. సిస్టమ్ ఆఫ్ చేస్తున్నాను.",
                "Locking your PC": "మీ PC లాక్ చేస్తున్నాను బాస్.",
                "Restarting your PC": "మీ PC రీస్టార్ట్ చేస్తున్నాను బాస్."
            }
            for eng, te_str in mapping.items():
                if eng in english_response:
                    return english_response.replace(eng, te_str)
            if "is open, Boss." in english_response:
                return english_response.replace("is open, Boss.", "ఓపెన్ చేశాను, Boss.")
            if "Opening" in english_response:
                return english_response.replace("Opening", "ఓపెన్ చేస్తున్నాను")
            if "Closing" in english_response:
                return english_response.replace("Closing", "క్లోజ్ చేస్తున్నాను")
            return english_response

        # 0. PERMANENTLY UNSUPPORTED DESTRUCTIVE COMMANDS SECURITY BLOCK
        # Factory Reset, Format Drive, and Delete All Files are permanently unsupported for security.
        for phrase in PERMANENTLY_UNSUPPORTED_PHRASES:
            if phrase in original or phrase in command:
                logger.warning(f"Permanently unsupported destructive command attempt blocked: '{original}'")
                log_security_audit("Destructive Command Attempt", "Permanently Disabled")
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                return "Sorry Boss. That operation is permanently disabled for security reasons."

        # 0A. TIMEOUT CHECK FOR PENDING CONFIRMATION
        if session.pending_confirmation:
            if session.is_confirmation_expired(timeout_seconds=15.0):
                pending_action = session.pending_confirmation.get("action", "")
                pending_cmd = session.pending_confirmation.get("command", "Unknown Command")
                log_security_audit(pending_cmd, "Timed Out")
                session.clear_pending_confirmation()
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                if pending_action == "shutdown_pc" or pending_cmd in ["shutdown pc", "shutdown computer", "turn off pc", "turn off computer", "power off computer", "power off windows"]:
                    return "Shutdown request timed out.\nOperation cancelled."
                return "Confirmation timed out."

        # 0B. MATCH DANGEROUS COMMAND REQUEST FIRST (OVERRIDE CHECK)
        matched_dangerous_key = None
        for key in DANGEROUS_COMMANDS:
            if key == original or key == command or key in original or key in command:
                if not is_ultron_shutdown(original, command):
                    matched_dangerous_key = key
                    break

        if matched_dangerous_key:
            display_name, requires_double, action_phrase, exec_func = DANGEROUS_COMMANDS[matched_dangerous_key]

            # Override existing pending confirmation if present
            if session.pending_confirmation:
                old_cmd = session.pending_confirmation.get("command", "Previous Command")
                log_security_audit(old_cmd, "Overridden")
                session.clear_pending_confirmation()

            # Set new pending confirmation with unique confirmation ID
            conf_data = session.set_pending_confirmation(
                action="shutdown_pc" if matched_dangerous_key in ["shutdown pc", "shutdown computer", "turn off pc", "turn off computer", "power off computer", "power off windows"] else display_name,
                command=matched_dangerous_key,
                requires_double=requires_double,
                action_phrase=action_phrase,
                exec_func=exec_func
            )
            logger.info(f"Initiated dangerous command confirmation [{conf_data['confirmation_id']}] for '{matched_dangerous_key}'")
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            if matched_dangerous_key in ["shutdown pc", "shutdown computer", "turn off pc", "turn off computer", "power off computer", "power off windows"]:
                return "Are you sure, Boss?\nYou requested to shut down your computer.\nPlease say 'Yes' to continue or 'Cancel' to abort."
            return "Are you sure, Boss?"

        # 0C. EVALUATE PENDING CONFIRMATION REPLIES
        if session.pending_confirmation:
            pending = session.pending_confirmation
            conf_id = pending["confirmation_id"]
            cmd_name = pending["command"]
            action_type = pending.get("action", "")
            step = pending["step"]
            requires_double = pending["requires_double"]
            action_phrase = pending["action_phrase"].lower()
            exec_func = pending["exec_func"]

            is_shutdown = action_type == "shutdown_pc" or cmd_name in ["shutdown pc", "shutdown computer", "turn off pc", "turn off computer", "power off computer", "power off windows"]

            if is_shutdown:
                shutdown_confirm_set = {"yes", "yes boss", "confirm", "continue", "proceed"}
                shutdown_cancel_set = {"no", "cancel", "stop", "never mind"}

                if original in shutdown_confirm_set or command in shutdown_confirm_set:
                    pending["validated"] = True
                    pending["confirmed"] = True
                    log_security_audit(cmd_name, "Confirmed")
                    confirm_msg = "Confirmation received.\nShutting down your computer.\nGoodbye, Boss."
                    try:
                        from voice.speech_output import speak
                        speak(confirm_msg)
                        session.session_data["_already_spoken"] = True
                    except Exception as e:
                        logger.error(f"TTS confirmation error: {e}")

                    if exec_func:
                        exec_func()
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return confirm_msg
                elif original in shutdown_cancel_set or command in shutdown_cancel_set:
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return "Shutdown cancelled, Boss."
                else:
                    # Unrelated command spoken while shutdown confirmation pending -> cancel & execute new command
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    logger.info("Pending shutdown confirmation cancelled due to unrelated command. Executing new command...")
                    new_res = self.process_command(original_command)
                    return f"Shutdown request cancelled.\n{new_res}"

            is_confirmed = original in CONFIRM_RESPONSES or command in CONFIRM_RESPONSES
            is_step2_confirmed = is_confirmed or (action_phrase in original or action_phrase in command)

            if step == 1:
                if is_confirmed:
                    if requires_double:
                        if not getattr(config, "DANGEROUS_COMMANDS_ENABLED", False):
                            log_security_audit(cmd_name, "Disabled")
                            session.clear_pending_confirmation()
                            event_bus.publish(event_bus.TASK_FINISHED, command=original)
                            return "This feature is disabled in the current production build."

                        pending["step"] = 2
                        pending["created_at"] = time.time()
                        event_bus.publish(event_bus.TASK_FINISHED, command=original)
                        return f"This action cannot be undone. Say '{pending['action_phrase']}' before execution."
                    else:
                        log_security_audit(cmd_name, "Confirmed")
                        session.clear_pending_confirmation()
                        res = exec_func() if exec_func else "Executed."
                        event_bus.publish(event_bus.TASK_FINISHED, command=original)
                        return "Confirmation received."
                elif original in CANCEL_RESPONSES or command in CANCEL_RESPONSES:
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return "Operation cancelled, Boss."
                else:
                    # Unrelated command spoken while confirmation pending -> cancel confirmation & execute new command
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    logger.info("Pending confirmation cancelled due to unrelated command. Proceeding with new command...")

            elif step == 2:
                if is_step2_confirmed:
                    if not getattr(config, "DANGEROUS_COMMANDS_ENABLED", False):
                        log_security_audit(cmd_name, "Disabled")
                        session.clear_pending_confirmation()
                        event_bus.publish(event_bus.TASK_FINISHED, command=original)
                        return "This feature is disabled in the current production build."

                    log_security_audit(cmd_name, "Confirmed")
                    session.clear_pending_confirmation()
                    res = exec_func() if exec_func else "Executed."
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return "Confirmation received."
                else:
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return "Operation cancelled, Boss."

        # 0D. ULTRON SHUTDOWN COMMANDS
        if is_ultron_shutdown(original, command):
            logger.info("Executing ULTRON Graceful Shutdown Sequence...")
            session.save()
            stop_speaking()
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
            session.reset()
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return "Goodbye Boss. Shutting down ULTRON."

        # 0E. SECURITY RESET & LOGOUT COMMANDS (REQUIREMENT 2)
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

        # 0D. DOMAIN AGENT DISPATCH VIA CENTRAL AGENT MANAGER
        agent_res = self._dispatch_to_domain_agent(command, original)
        if agent_res is not None:
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return _format_local_response(agent_res)

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
        if any(k in command for k in ["d drive", "c drive", "tell about d drive", "tell about c drive", "disk status", "storage status", "d: drive", "c: drive", "my storage", "my disk"]):
            target = "D" if ("d drive" in command or "d:" in command) else ("C" if ("c drive" in command or "c:" in command) else None)
            return system_control.get_disk_info(target)
        if any(k in command for k in ["tell my system", "tell me my system", "what is my system", "system details", "system info", "system information", "system specs", "hardware info", "hardware details", "cpu and ram", "my hardware"]):
            return system_control.get_system_info()
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

        # 9. BASIC CHAT RESPONSES
        basic_chat = self._chat_response(command)
        if basic_chat is not None:
            return _format_local_response(basic_chat)

        # 10. LANGUAGE DETECTION & LLM FALLBACK
        llm_prompt = command
        if current_lang == "te":
            llm_prompt = "User is speaking Telugu (or transliterated Tanglish). You MUST reply in natural conversational Telugu script. Understand transliterated Tanglish semantically. Do not perform word-for-word transliteration. Do not invent meanings. User query: " + command
            
        result = llm_manager.ask(llm_prompt)
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
