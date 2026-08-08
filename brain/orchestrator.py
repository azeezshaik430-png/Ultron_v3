"""
ULTRON V3 - Central Brain Orchestrator
The single brain controller of ULTRON V3.
All user inputs flow strictly through Orchestrator -> Intent -> Planner -> Router -> Skills/LLM.
"""

import time
import webbrowser
import urllib.parse
from typing import Optional, Dict, Any, Tuple

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
    "power off pc": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),
    "shutdown my pc": ("Shutdown PC", False, "CONFIRM SHUTDOWN", shutdown_pc),

    "restart pc": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "restart computer": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "reboot pc": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "reboot computer": ("Restart PC", False, "CONFIRM RESTART", restart_pc),
    "restart my pc": ("Restart PC", False, "CONFIRM RESTART", restart_pc),

    "sign out": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),
    "log out windows": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),
    "sign me out": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),
    "sign out my pc": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),
    "log out my pc": ("Sign Out", False, "CONFIRM SIGNOUT", sign_out_pc),

    "lock pc": ("Lock PC", False, "CONFIRM LOCK", lock_pc),
    "lock computer": ("Lock PC", False, "CONFIRM LOCK", lock_pc),
    "lock my pc": ("Lock PC", False, "CONFIRM LOCK", lock_pc),

    "sleep pc": ("Sleep PC", False, "CONFIRM SLEEP", sleep_pc),
    "sleep computer": ("Sleep PC", False, "CONFIRM SLEEP", sleep_pc),
    "sleep my pc": ("Sleep PC", False, "CONFIRM SLEEP", sleep_pc),
    "put pc to sleep": ("Sleep PC", False, "CONFIRM SLEEP", sleep_pc),
    "put computer to sleep": ("Sleep PC", False, "CONFIRM SLEEP", sleep_pc),
}


def is_deterministic_command(cmd: str) -> bool:
    c = cmd.lower().strip()
    
    # Volume commands
    if c in ["volume up", "increase volume", "volume penchu", "volume penchandi", "volume down", "decrease volume", "volume tagginchu", "volume tagginchandi", "mute", "mute volume", "mute cheyyi", "mute chey", "unmute", "unmute volume", "unmute cheyyi", "unmute chey"]:
        return True
    if c.startswith("set volume to ") or ("volume" in c and "percent" in c):
        return True
        
    # Dangerous session commands
    dangerous_triggers = [
        "shutdown", "turn off pc", "turn off computer", "power off",
        "restart", "reboot", "sign out", "log out", "lock pc", "lock computer",
        "sleep pc", "sleep computer", "sleep my pc"
    ]
    if any(k in c for k in dangerous_triggers):
        return True
        
    # Browser commands
    browser_triggers = [
        "open ", "go to ", "navigate to ", "visit ", "search ", "play ",
        "come back", "go back", "back", "return", "close browser", "close tab", "close page", "close youtube", "close whatsapp"
    ]
    browser_suffixes = ["open cheyyi", "close cheyyi", "open chey", "close chey", "search cheyyi", "search chey", "play cheyyi", "play chey"]
    if any(c.startswith(k) for k in browser_triggers) or any(c.endswith(s) for s in browser_suffixes):
        return True
        
    # Conversational replies like "yes" or "cancel" if pending confirmation is active
    if c in ["yes", "no", "cancel", "confirm", "proceed", "yes boss", "cancel cheyyi", "vaddu"]:
        return True
        
    return False


def parse_search_command(cmd: str, current_url: str) -> Tuple[str, str]:
    cmd_lower = cmd.lower().strip()
    
    # Strip "search for ", "search ", " search cheyyi", " search chey"
    clean_query = cmd_lower
    for term in ["search for ", "search in ", "search on ", "search "]:
        if clean_query.startswith(term):
            clean_query = clean_query[len(term):].strip()
            break
            
    for suffix in [" search cheyyi", " search chey", " search"]:
        if clean_query.endswith(suffix):
            clean_query = clean_query[:-len(suffix)].strip()
            break
            
    # Detect site in cmd_lower
    site = None
    if "youtube" in cmd_lower:
        site = "youtube"
        # Strip "youtube" and connectors
        for term in ["youtube for ", "youtube in ", "youtube on ", "youtube "]:
            if clean_query.startswith(term):
                clean_query = clean_query[len(term):].strip()
        for term in [" in youtube", " on youtube", " youtube"]:
            if clean_query.endswith(term):
                clean_query = clean_query[:-len(term)].strip()
    elif "google" in cmd_lower:
        site = "google"
        for term in ["google for ", "google in ", "google on ", "google "]:
            if clean_query.startswith(term):
                clean_query = clean_query[len(term):].strip()
        for term in [" in google", " on google", " google"]:
            if clean_query.endswith(term):
                clean_query = clean_query[:-len(term)].strip()
    elif "github" in cmd_lower:
        site = "github"
        for term in ["github for ", "github "]:
            if clean_query.startswith(term):
                clean_query = clean_query[len(term):].strip()
        for term in [" in github", " github"]:
            if clean_query.endswith(term):
                clean_query = clean_query[:-len(term)].strip()
                
    # If no site detected in command, check current_url
    if not site:
        if "youtube.com" in current_url:
            site = "youtube"
        else:
            site = "google" # Default fallback
            
    return site, clean_query


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
        
        is_browser_command = False
        b_action = "open_url"
        target_url = ""
        
        # Priority 1: Check Search Intent BEFORE generic open_url
        is_search_intent = False
        search_site = None
        search_query = None
        
        if orig.startswith("search ") or "search " in orig or "search cheyyi" in orig or "search chey" in orig:
            is_search_intent = True
            active_url = getattr(self._browser_agent, "current_url", "")
            search_site, search_query = parse_search_command(original, active_url)
            logger.info(f"[Orchestrator] _dispatch_to_domain_agent parsed search intent: site='{search_site}', query='{search_query}'")

        if any(k in orig for k in ["search something else", "search again", "malli search", "something else search"]):
            session.session_data["browser_state"] = "WAITING_FOR_SEARCH_QUERY"
            current_lang = getattr(session, "preferred_language", "en")
            return "What would you like me to search for, Boss?" if current_lang != "te" else "ఏం search చేయాలి Boss?"
        elif "come back and search " in orig or "back ki velli " in orig or "venakki velli " in orig or "malli velli " in orig or "back and search" in orig:
            is_browser_command = True
            b_action = "back_and_search"
        elif orig in ["come back", "go back", "back", "back ki velli", "back ki vellu", "return"]:
            is_browser_command = True
            b_action = "go_back"
        elif "play" in orig and any(ord in orig for ord in ["first", "second", "third", "fourth", "fifth", "1st", "2nd", "3rd", "4th", "5th", "modati", "rendava", "moodava", "play cheyyi", "play chey"]):
            is_browser_command = True
            b_action = "play_nth_video"
        elif orig in ["close browser", "close tab", "close page", "close youtube", "close whatsapp", "close brave"]:
            is_browser_command = True
            b_action = "close_browser"
        elif is_search_intent and search_query:
            is_browser_command = True
            b_action = "search_site"
        elif any(orig.startswith(k) for k in ["open ", "go to ", "navigate to ", "visit "]) or any(orig.endswith(s) for s in [" open cheyyi", " open chey"]):
            target_term = orig
            for kw in ["open ", "go to ", "navigate to ", "visit "]:
                if target_term.startswith(kw):
                    target_term = target_term[len(kw):].strip()
                    break
            for sfx in [" open cheyyi", " open chey"]:
                if target_term.endswith(sfx):
                    target_term = target_term[:-len(sfx)].strip()
                    break
            
            if target_term == "brave":
                session.session_data["browser_state"] = "WAITING_FOR_WEBSITE"
                res = self.agent_manager.dispatch_task("browser_agent", t_id, {
                    "action": "open_url",
                    "url": "about:blank",
                })
                current_lang = getattr(session, "preferred_language", "en")
                if current_lang == "te":
                    return "ఏ website open చేయాలి Boss?"
                return "What website would you like me to open, Boss?"
            elif target_term in KNOWN_WEBSITES:
                is_browser_command = True
                b_action = "open_url"
                target_url = KNOWN_WEBSITES[target_term]
            elif "." in target_term and not " " in target_term:
                is_browser_command = True
                b_action = "open_url"
                target_url = "https://" + target_term if not target_term.startswith("http") else target_term
            elif target_term in ["browser", "tab", "page", "website"]:
                is_browser_command = True
                b_action = "open_url"
                target_url = "about:blank"
        
        # If matches browser command, execute it deterministically!
        if is_browser_command:
            t_start_browser = time.perf_counter()
            logger.info(f"[Orchestrator] Browser intent detected: {b_action}")
            current_lang = getattr(session, "preferred_language", "en")
            
            if b_action == "search_site":
                query_escaped = urllib.parse.quote_plus(search_query)
                if search_site == "youtube":
                    target_url = f"https://www.youtube.com/results?search_query={query_escaped}"
                elif search_site == "google":
                    target_url = f"https://www.google.com/search?q={query_escaped}"
                else:
                    target_url = f"https://www.google.com/search?q=site:{search_site}.com+{query_escaped}"
                b_action = "open_url"

            elif b_action == "back_and_search":
                # First go back
                res = self.agent_manager.dispatch_task("browser_agent", t_id, {"action": "go_back"})
                if res.get("status") == "SUCCESS":
                    # Get current URL
                    res_url = self.agent_manager.dispatch_task("browser_agent", t_id, {"action": "get_url"})
                    returned_url = res_url.get("result", {}).get("url", "") if res_url.get("status") == "SUCCESS" else ""
                    
                    # Extract query
                    query = ""
                    if " and search " in orig:
                        query = original[orig.find(" and search ") + 12:].strip()
                    elif "search cheyyi" in orig:
                        if "velli " in orig:
                            query = original[orig.find("velli ") + 6:orig.find(" search")].strip()
                        else:
                            query = original[orig.find("and ") + 4:orig.find(" search")].strip()
                    if not query:
                        query = "Python tutorials"
                        
                    target_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                    search_target = "Google"
                    if "youtube.com" in returned_url:
                        target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
                        search_target = "YouTube"
                        
                    res = self.agent_manager.dispatch_task("browser_agent", t_id, {
                        "action": "open_url",
                        "url": target_url
                    })
                    b_action = "open_url"
                else:
                    return f"I couldn't complete the browser action because back failed: {res.get('reason')}"
            
            payload = {"action": b_action, "url": target_url or "https://example.com"}
            
            if b_action == "play_nth_video":
                idx = 0
                lower_orig = orig.lower()
                if "first" in lower_orig or "1st" in lower_orig or "modati" in lower_orig: idx = 0
                elif "second" in lower_orig or "2nd" in lower_orig or "rendava" in lower_orig: idx = 1
                elif "third" in lower_orig or "3rd" in lower_orig or "moodava" in lower_orig: idx = 2
                elif "fourth" in lower_orig or "4th" in lower_orig or "nalgava" in lower_orig: idx = 3
                elif "fifth" in lower_orig or "5th" in lower_orig or "aidava" in lower_orig: idx = 4
                elif "sixth" in lower_orig or "6th" in lower_orig: idx = 5
                payload["index"] = idx
                
            res = self.agent_manager.dispatch_task("browser_agent", t_id, payload)
            
            if res.get("status") == "SUCCESS":
                inner = res.get("result", {})
                inner_status = inner.get("status") if isinstance(inner, dict) else "SUCCESS"
                reason = inner.get("reason", "") if isinstance(inner, dict) else ""
                
                if inner_status == "ERROR":
                    return f"I couldn't complete the browser action because {reason}"
                    
                if b_action == "open_url":
                    title = inner.get('title', target_url)
                    # Strip URL if title is just raw URL
                    if isinstance(title, str) and title.startswith("http"):
                        title = "Website"
                    if "youtube.com/results" in target_url or "youtube.com" in target_url:
                        title = "YouTube"
                    if "web.whatsapp.com" in target_url or "whatsapp" in target_url:
                        title = "WhatsApp Web"
                    if current_lang == "te":
                        return f"{title} ఓపెన్ చేశాను, Boss."
                    return f"{title} is open, Boss."
                elif b_action == "close_browser":
                    if current_lang == "te":
                        return "Browser క్లోజ్ చేశాను, Boss."
                    return "The browser has been closed."
                elif b_action == "go_back":
                    if current_lang == "te":
                        return "వెనక్కి వెళ్ళాను బాస్."
                    return "Navigated back, Boss."
                elif b_action == "play_nth_video":
                    v_title = inner.get("title", "video")
                    ordinal = ["first", "second", "third", "fourth", "fifth"][payload["index"]] if payload["index"] < 5 else "nth"
                    if current_lang == "te":
                        return f"Playing the {ordinal} video, Boss."
                    return f"Playing the {ordinal} video, Boss."
            else:
                return f"I couldn't complete the browser action because: {res.get('reason')}"
        return None

    def _log_latency_instrumentation(self, command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end):
        t_end = time.perf_counter()
        end_to_end_latency_ms = (t_end - t_stt_end) * 1000.0
        logger.info("==================================================")
        logger.info("⏱️ [ULTRON LATENCY INSTRUMENTATION]")
        logger.info(f"   command_latency_ms:    {command_latency_ms:.2f} ms")
        logger.info(f"   action_latency_ms:     {action_latency_ms:.2f} ms")
        logger.info(f"   llm_latency_ms:        {llm_latency_ms:.2f} ms")
        logger.info(f"   tts_latency_ms:        {tts_latency_ms:.2f} ms")
        logger.info(f"   end_to_end_latency_ms: {end_to_end_latency_ms:.2f} ms")
        logger.info("==================================================")

    def process_command(self, original_command: str) -> str:
        """
        Master input execution pipeline:
        Input -> Security/Memory -> Domain Agent / Skill / Intent -> LLM Fallback -> Response
        """
        t_stt_end = time.perf_counter()
        logger.info(f"[Instrumentation] STT_END at {t_stt_end:.4f}")

        # Initialize default latency metrics
        command_latency_ms = 0.0
        action_latency_ms = 0.0
        llm_latency_ms = 0.0
        tts_latency_ms = 0.0

        if not original_command:
            return "Waiting Boss"

        original = original_command.lower().strip()
        command = clean_command(original)

        if not command and not original:
            return "Waiting Boss"

        logger.info(f"Processing Command: '{original}' (cleaned: '{command}')")

        # Multi-Action Decomposition
        if " and " in original:
            parts = [p.strip() for p in original.split(" and ")]
            if len(parts) > 1 and all(is_deterministic_command(p) for p in parts):
                logger.info(f"[Orchestrator] Decomposing multi-action command: {parts}")
                results = []
                for part in parts:
                    res = self.process_command(part)
                    results.append(res)
                    if any(k in res for k in ["Cannot", "Failed", "Security block", "unauthorized", "invalid", "failed"]):
                        logger.warning(f"[Orchestrator] Multi-action aborted due to failure: {res}")
                        break
                return " and ".join(results)

        # Ignore "yes"/"cancel" if no state is pending
        if original in ["yes", "no", "cancel", "confirm", "proceed", "cancel cheyyi", "vaddu"]:
            if not session.pending_confirmation and not session.session_data.get("browser_state"):
                logger.info(f"Command '{original}' ignored because no confirmation/conversational state is pending.")
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                return "Waiting Boss"
        
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
            
        # 0. DIRECT LOCAL ROUTING (SYSTEM & VOLUME)
        # Bypass LLM completely for deterministic system controls
        vol_lower = original
        if vol_lower in ["volume up", "increase volume", "volume penchu", "volume penchandi"]:
            t_act_start = time.perf_counter()
            res = self._system_agent._do_execute_task("volume", {"action": "volume_up"})
            action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
            command_latency_ms = (t_act_start - t_stt_end) * 1000.0
            self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
            return res
        elif vol_lower in ["volume down", "decrease volume", "volume tagginchu", "volume tagginchandi"]:
            t_act_start = time.perf_counter()
            res = self._system_agent._do_execute_task("volume", {"action": "volume_down"})
            action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
            command_latency_ms = (t_act_start - t_stt_end) * 1000.0
            self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
            return res
        elif vol_lower in ["mute", "mute volume", "mute cheyyi", "mute chey"]:
            t_act_start = time.perf_counter()
            res = self._system_agent._do_execute_task("volume", {"action": "mute"})
            action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
            command_latency_ms = (t_act_start - t_stt_end) * 1000.0
            self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
            return res
        elif vol_lower in ["unmute", "unmute volume", "unmute cheyyi", "unmute chey"]:
            t_act_start = time.perf_counter()
            res = self._system_agent._do_execute_task("volume", {"action": "unmute"})
            action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
            command_latency_ms = (t_act_start - t_stt_end) * 1000.0
            self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
            return res
        elif vol_lower.startswith("set volume to ") or ("volume" in vol_lower and "percent" in vol_lower):
            import re
            match = re.search(r'\b(\d+)\b', vol_lower)
            if match:
                t_act_start = time.perf_counter()
                res = self._system_agent._do_execute_task("volume", {"action": "set_volume", "level": int(match.group(1))})
                action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
                command_latency_ms = (t_act_start - t_stt_end) * 1000.0
                self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
                return res

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

            # Map action correctly
            mapped_action = "shutdown_pc"
            if "restart" in matched_dangerous_key or "reboot" in matched_dangerous_key:
                mapped_action = "restart_pc"
            elif "sign out" in matched_dangerous_key or "log out" in matched_dangerous_key or "sign me out" in matched_dangerous_key:
                mapped_action = "sign_out_pc"
            elif "sleep" in matched_dangerous_key:
                mapped_action = "sleep_pc"
            elif "lock" in matched_dangerous_key:
                mapped_action = "lock_pc"
                
            # Set new pending confirmation with unique confirmation ID
            conf_data = session.set_pending_confirmation(
                action=mapped_action,
                command=matched_dangerous_key,
                requires_double=requires_double,
                action_phrase=action_phrase,
                exec_func=exec_func
            )
            logger.info(f"Initiated dangerous command confirmation [{conf_data['confirmation_id']}] for '{matched_dangerous_key}'")
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            
            action_noun = "shut down your computer"
            if mapped_action == "restart_pc":
                action_noun = "restart your computer"
            elif mapped_action == "sign_out_pc":
                action_noun = "sign out of your computer"
            elif mapped_action == "sleep_pc":
                action_noun = "put your computer to sleep"
            elif mapped_action == "lock_pc":
                action_noun = "lock your computer"

            return f"Are you sure, Boss?\nYou requested to {action_noun}.\nPlease say 'Yes' to continue or 'Cancel' to abort."

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

            is_dangerous_action = action_type in ["shutdown_pc", "restart_pc", "sign_out_pc", "sleep_pc", "lock_pc"]

            if is_dangerous_action:
                confirm_set = CONFIRM_RESPONSES
                cancel_set = CANCEL_RESPONSES

                if original in confirm_set or command in confirm_set:
                    pending["validated"] = True
                    pending["confirmed"] = True
                    log_security_audit(cmd_name, "Confirmed")
                    
                    if action_type == "shutdown_pc":
                        confirm_msg = "Confirmation received.\nShutting down your computer.\nGoodbye, Boss."
                    elif action_type == "restart_pc":
                        confirm_msg = "Confirmation received.\nRestarting your computer.\nGoodbye, Boss."
                    elif action_type == "sign_out_pc":
                        confirm_msg = "Confirmation received.\nSigning out of your computer.\nGoodbye, Boss."
                    elif action_type == "sleep_pc":
                        confirm_msg = "Confirmation received.\nPutting your computer to sleep, Boss."
                    elif action_type == "lock_pc":
                        confirm_msg = "Confirmation received.\nLocking your computer, Boss."
                    else:
                        confirm_msg = "Confirmation received, Boss."

                    t_act_start = time.perf_counter()
                    res = None
                    if exec_func:
                        res = exec_func()
                    action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
                    command_latency_ms = (t_act_start - t_stt_end) * 1000.0

                    action_failed = False
                    if isinstance(res, str) and ("Security block" in res or "Cannot" in res or "failed" in res or "Blocked" in res):
                        action_failed = True
                        confirm_msg = f"Failed to execute action, Boss: {res}"
                        log_security_audit(cmd_name, f"Failed: {res}")
                        session.clear_pending_confirmation()
                    else:
                        try:
                            from voice.speech_output import speak
                            speak(confirm_msg)
                            session.session_data["_already_spoken"] = True
                        except Exception as e:
                            logger.error(f"TTS confirmation error: {e}")
                        session.clear_pending_confirmation()

                    self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
                    return confirm_msg
                elif original in cancel_set or command in cancel_set:
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    action_noun = "Action"
                    if action_type == "shutdown_pc":
                        action_noun = "Shutdown"
                    elif action_type == "restart_pc":
                        action_noun = "Restart"
                    elif action_type == "sign_out_pc":
                        action_noun = "Sign out"
                    elif action_type == "sleep_pc":
                        action_noun = "Sleep"
                    elif action_type == "lock_pc":
                        action_noun = "Lock"
                    return f"{action_noun} cancelled, Boss."
                else:
                    log_security_audit(cmd_name, "Cancelled")
                    session.clear_pending_confirmation()
                    logger.info("Pending dangerous action confirmation cancelled due to unrelated command. Executing new command...")
                    new_res = self.process_command(original_command)
                    return f"Action cancelled.\n{new_res}"

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
                        pending["validated"] = True
                        pending["confirmed"] = True
                        res = exec_func() if exec_func else "Confirmation received."
                        session.clear_pending_confirmation()
                        event_bus.publish(event_bus.TASK_FINISHED, command=original)
                        return str(res)
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
                    pending["validated"] = True
                    pending["confirmed"] = True
                    res = exec_func() if exec_func else "Confirmation received."
                    session.clear_pending_confirmation()
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return str(res)
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
            session.session_data.pop("browser_state", None)
            session.session_data.pop("browser_target", None)
            session.reset()
            event_bus.publish(event_bus.TASK_FINISHED, command=original)
            return "Goodbye Boss. Shutting down ULTRON."

        # 0E. SECURITY RESET & LOGOUT COMMANDS (REQUIREMENT 2)
        if command in ["logout", "lock ultron"] or original in ["logout", "lock ultron"]:
            logger.info("Executing Security Logout & Sleep Sequence...")
            session.set_auth(False)
            stop_speaking()
            session.session_data.pop("browser_state", None)
            session.session_data.pop("browser_target", None)
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

        import urllib.parse
        # 0F. CONVERSATIONAL BROWSER STATE MACHINE
        browser_state = session.session_data.get("browser_state")
        
        # Check if the command is an explicit top-level command that should override pending state.
        # This prevents "open whatsapp" or "close youtube" from being treated as a search query.
        is_explicit_override = False
        if browser_state:
            if is_deterministic_command(original) and not any(k in original for k in ["cancel", "never mind", "stop", "vaddu", "cancel cheyyi", "yes", "confirm", "proceed", "no"]):
                is_explicit_override = True
                logger.info(f"Explicit command '{original}' overriding pending browser state.")
                session.session_data.pop("browser_state", None)
                session.session_data.pop("browser_target", None)
                browser_state = None

        if browser_state:
            # Check for cancellation
            cancel_triggers = ["cancel", "never mind", "stop", "vaddu", "cancel cheyyi"]
            if any(k in original for k in cancel_triggers):
                session.session_data.pop("browser_state", None)
                session.session_data.pop("browser_target", None)
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                return "Cancelled, Boss." if current_lang != "te" else "క్యాన్సిల్ చేశాను బాస్."

            if browser_state == "WAITING_FOR_WEBSITE":
                target_url = original
                # KNOWN_WEBSITES is duplicated here for quick resolution
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
                
                # Check for direct match
                resolved_key = None
                for key in KNOWN_WEBSITES:
                    if key in original:
                        resolved_key = key
                        break
                        
                if not resolved_key:
                    # Invalid input, clear state
                    session.session_data.pop("browser_state", None)
                    session.session_data.pop("browser_target", None)
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return "I don't recognize that website. Navigation cancelled." if current_lang != "te" else "ఆ వెబ్‌సైట్ నాకు తెలియదు. క్యాన్సిల్ చేశాను."
                    
                target_url = KNOWN_WEBSITES[resolved_key]
                t_id = f"task_{int(time.time() * 1000)}"
                t_act_start = time.perf_counter()
                res = self.agent_manager.dispatch_task("browser_agent", t_id, {
                    "action": "open_url",
                    "url": target_url,
                })
                action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
                command_latency_ms = (t_act_start - t_stt_end) * 1000.0
                self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
                
                if res.get("status") == "SUCCESS" and res.get("result", {}).get("status") != "ERROR":
                    searchable = ["youtube", "google", "github", "x", "twitter"]
                    if resolved_key in searchable:
                        session.session_data["browser_state"] = "WAITING_FOR_SEARCH_QUERY"
                        session.session_data["browser_target"] = resolved_key
                        event_bus.publish(event_bus.TASK_FINISHED, command=original)
                        if current_lang == "te":
                            return f"{resolved_key.capitalize()} లో ఏం search చేయాలి Boss?"
                        return f"What would you like me to search for on {resolved_key.capitalize()}, Boss?"
                    else:
                        session.session_data.pop("browser_state", None)
                        session.session_data.pop("browser_target", None)
                        event_bus.publish(event_bus.TASK_FINISHED, command=original)
                        title = res.get("result", {}).get("title", resolved_key.capitalize())
                        return f"{title} is open, Boss." if current_lang != "te" else f"{title} ఓపెన్ చేశాను, Boss."
                else:
                    session.session_data.pop("browser_state", None)
                    session.session_data.pop("browser_target", None)
                    event_bus.publish(event_bus.TASK_FINISHED, command=original)
                    return f"I couldn't open {resolved_key.capitalize()} because {res.get('reason', res.get('result', {}).get('reason', 'unknown error'))}"
                    
            elif browser_state == "WAITING_FOR_SEARCH_QUERY":
                target_site = session.session_data.get("browser_target")
                query = urllib.parse.quote_plus(original)
                
                search_url = ""
                if target_site == "youtube":
                    search_url = f"https://www.youtube.com/results?search_query={query}"
                elif target_site == "google":
                    search_url = f"https://www.google.com/search?q={query}"
                elif target_site in ["github", "twitter", "x"]:
                    # Adjust if needed, fallback to basic google search if unknown
                    search_url = f"https://www.google.com/search?q=site:{target_site}.com+{query}"
                    
                t_id = f"task_{int(time.time() * 1000)}"
                t_act_start = time.perf_counter()
                res = self.agent_manager.dispatch_task("browser_agent", t_id, {
                    "action": "open_url",
                    "url": search_url,
                })
                action_latency_ms = (time.perf_counter() - t_act_start) * 1000.0
                command_latency_ms = (t_act_start - t_stt_end) * 1000.0
                self._log_latency_instrumentation(command_latency_ms, action_latency_ms, llm_latency_ms, tts_latency_ms, t_stt_end)
                
                session.session_data.pop("browser_state", None)
                session.session_data.pop("browser_target", None)
                event_bus.publish(event_bus.TASK_FINISHED, command=original)
                
                if res.get("status") == "SUCCESS" and res.get("result", {}).get("status") != "ERROR":
                    if current_lang == "te":
                        return "వెతుకుతున్నాను బాస్."
                    return f"Searching for {original} on {target_site.capitalize()}, Boss."
                else:
                    return f"I couldn't complete the search because {res.get('reason', res.get('result', {}).get('reason', 'unknown error'))}"

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
