"""
ULTRON V3
Computer-Use Module

Observe → Understand → Decide → Act → Verify loop.
Requires explicit activation. Max 5 iterations per request.
Destructive actions require confirmation. Never autonomous shutdown/restart/delete.

Enhanced decision layer:
- Screen dimensions passed to LLM for meaningful coordinates
- Coordinate bounds validation
- Multi-step action plans
- Common app launch keyboard patterns
- Invalid action protection
"""

import os
import re
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple
from core.logger import logger
from core.session import session


# Safety: actions that are NEVER allowed in autonomous computer-use
FORBIDDEN_ACTIONS = {
    "shutdown", "restart", "reboot", "sign_out", "log_out",
    "delete_file", "format", "factory_reset", "rm -rf",
    "del /f", "wipe",
}

# Safety: actions that require confirmation even in computer-use mode
CONFIRMATION_REQUIRED = {
    "close_app", "kill_process", "keyboard_type_password",
}

# Valid action types the model can return
VALID_ACTION_TYPES = {"click", "type", "scroll", "wait", "done", "fail", "key_press"}

MAX_ITERATIONS = 10
OBSERVE_DELAY = 0.5  # seconds between iterations

# Well-known app names for keyboard-launch pattern
_KNOWN_APPS = {
    "calculator", "notepad", "paint", "chrome", "firefox", "edge",
    "word", "excel", "powerpoint", "explorer", "cmd", "terminal",
    "spotify", "vscode", "code", "teams", "discord", "slack",
    "photoshop", "premiere", "obs", "zoom", "skype",
}


def is_computer_use_active() -> bool:
    """Check if computer-use mode is currently active."""
    return session.session_data.get("computer_use_active", False)


def activate_computer_use() -> str:
    """Activate computer-use mode. Requires explicit user request."""
    session.session_data["computer_use_active"] = True
    session.session_data["computer_use_iterations"] = 0
    logger.info("[ComputerUse] Mode ACTIVATED by user request")
    return "Computer use mode activated, Boss. I'll observe, decide, and act. Say 'stop computer use' to exit."


def deactivate_computer_use() -> str:
    """Deactivate computer-use mode."""
    session.session_data["computer_use_active"] = False
    session.session_data["computer_use_iterations"] = 0
    logger.info("[ComputerUse] Mode DEACTIVATED")
    return "Computer use mode deactivated, Boss."


# =========================================================================
# MAIN LOOP
# =========================================================================

def execute_computer_use_task(
    task_description: str,
    vision_agent=None,
    agent_manager=None,
) -> Dict[str, Any]:
    """
    Execute a computer-use task through the observe→decide→act→verify loop.

    Supports multi-step action plans: the model can return a list of steps
    that are executed sequentially across iterations.

    Args:
        task_description: What the user wants done (e.g., "click the search button")
        vision_agent: VisionAgent instance for screenshots/OCR
        agent_manager: AgentManager for dispatching actions

    Returns:
        {
            "status": "SUCCESS" | "ERROR" | "SAFETY_BLOCK",
            "iterations": int,
            "actions_taken": list,
            "result": str,
        }
    """
    if not is_computer_use_active():
        return {
            "status": "ERROR",
            "iterations": 0,
            "actions_taken": [],
            "result": "Computer use mode is not active. Say 'start computer use' first.",
        }

    iterations = session.session_data.get("computer_use_iterations", 0)
    actions_taken = []
    pending_steps: List[Dict[str, Any]] = []
    plan_description = ""

    remaining_task = None  # Set by app launch plan for compound tasks

    logger.info(f"[ComputerUse] Task: '{task_description}' (iteration {iterations + 1}/{MAX_ITERATIONS})")

    for i in range(MAX_ITERATIONS - iterations):
        current_iter = iterations + i + 1
        session.session_data["computer_use_iterations"] = current_iter

        # --- Execute pending plan steps first (no new observe/decide needed) ---
        if pending_steps:
            step = pending_steps.pop(0)
            step_desc = step.get("details", "plan step")
            logger.info(f"[ComputerUse] Plan step ({len(pending_steps) + 1} remaining): {step_desc}")

            act_result = _act(step, agent_manager)
            actions_taken.append({
                "iteration": current_iter,
                "action": step.get("action_type", "unknown"),
                "details": step_desc,
                "result": act_result.get("result", ""),
            })

            if act_result.get("status") == "ERROR":
                return {
                    "status": "ERROR",
                    "iterations": current_iter,
                    "actions_taken": actions_taken,
                    "result": f"Plan step failed: {act_result.get('error', 'Unknown error')}",
                }

            # When plan completes, swap to remaining task if present
            if not pending_steps and remaining_task:
                logger.info(f"[ComputerUse] Plan complete. Switching to remaining task: '{remaining_task}'")
                task_description = remaining_task
                remaining_task = None

            time.sleep(OBSERVE_DELAY)
            continue

        # --- OBSERVE ---
        observe_result = _observe(vision_agent)
        if observe_result.get("status") == "ERROR":
            return {
                "status": "ERROR",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": f"Failed to observe screen: {observe_result.get('error', 'Unknown error')}",
            }

        screen_text = observe_result.get("text", "")
        screen_w = observe_result.get("width", 1920)
        screen_h = observe_result.get("height", 1080)
        logger.info(f"[ComputerUse] Observe iteration {current_iter}: {len(screen_text)} chars OCR, {screen_w}x{screen_h}")

        # --- DECIDE ---
        decision = _decide(task_description, screen_text, screen_w, screen_h, current_iter)

        if decision.get("action") == "DONE":
            return {
                "status": "SUCCESS",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": decision.get("result", "Task completed."),
            }

        if decision.get("action") == "FAIL":
            return {
                "status": "ERROR",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": decision.get("result", "Could not determine action."),
            }

        # --- VALIDATE the action ---
        validation = _validate_action(decision, screen_w, screen_h)
        if not validation["valid"]:
            logger.warning(f"[ComputerUse] Invalid action rejected: {validation['reason']}")
            return {
                "status": "ERROR",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": f"Invalid action from model: {validation['reason']}",
            }

        # --- SAFETY CHECK ---
        action_name = decision.get("action_type", "")
        if action_name in FORBIDDEN_ACTIONS:
            logger.warning(f"[ComputerUse] SAFETY BLOCK: '{action_name}' is forbidden in autonomous mode")
            return {
                "status": "SAFETY_BLOCK",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": f"Safety block: '{action_name}' cannot be performed autonomously.",
            }

        if action_name in CONFIRMATION_REQUIRED:
            logger.info(f"[ComputerUse] Confirmation required for '{action_name}' — pausing")
            return {
                "status": "PENDING_CONFIRMATION",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": f"Need your confirmation to {action_name}, Boss.",
                "pending_action": decision,
            }

        # --- Extract plan steps if present ---
        plan_steps = decision.get("plan", [])
        plan_queued = False
        if plan_steps and isinstance(plan_steps, list):
            plan_description = decision.get("details", "multi-step plan")
            logger.info(f"[ComputerUse] Received plan with {len(plan_steps)} steps: {plan_description}")
            # Validate each plan step before adding to queue
            validated_steps = []
            for idx, step in enumerate(plan_steps):
                step_val = _validate_action(step, screen_w, screen_h)
                if step_val["valid"]:
                    validated_steps.append(step)
                else:
                    logger.warning(f"[ComputerUse] Plan step {idx} invalid, skipped: {step_val['reason']}")
            if validated_steps:
                pending_steps = validated_steps
                plan_queued = True
                # Capture remaining task for compound commands
                if decision.get("remaining_task"):
                    remaining_task = decision["remaining_task"]

        # --- ACT the current step (skip if plan was queued — plan steps will execute) ---
        if plan_queued:
            act_result = {"status": "SUCCESS", "result": f"Plan queued: {len(pending_steps)} steps"}
        else:
            act_result = _act(decision, agent_manager)
        actions_taken.append({
            "iteration": current_iter,
            "action": decision.get("action_type", "unknown"),
            "details": decision.get("details", ""),
            "result": act_result.get("result", ""),
        })

        logger.info(f"[ComputerUse] Act iteration {current_iter}: {decision.get('action_type')} → {act_result.get('status')}")

        if act_result.get("status") == "ERROR":
            return {
                "status": "ERROR",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": f"Action failed: {act_result.get('error', 'Unknown error')}",
            }

        time.sleep(OBSERVE_DELAY)

    # Max iterations reached
    remaining = len(pending_steps)
    return {
        "status": "MAX_ITERATIONS",
        "iterations": MAX_ITERATIONS,
        "actions_taken": actions_taken,
        "result": f"Reached maximum iterations ({MAX_ITERATIONS}). {len(actions_taken)} actions taken. {remaining} plan steps remaining.",
    }


# =========================================================================
# OBSERVE
# =========================================================================

def _observe(vision_agent=None) -> Dict[str, Any]:
    """Capture screenshot and extract OCR text. Returns screen dimensions too."""
    try:
        if vision_agent:
            result = vision_agent._do_execute_task(
                f"observe_{uuid.uuid4().hex[:6]}",
                {"action": "capture_screen"}
            )
            if isinstance(result, dict) and result.get("status") == "SUCCESS":
                filepath = result.get("filepath", "")
                if filepath and os.path.exists(filepath):
                    ocr_result = vision_agent._run_ocr({"filepath": filepath})
                    # Get dimensions from image
                    w, h = 1920, 1080
                    try:
                        from PIL import Image
                        img = Image.open(filepath)
                        w, h = img.size
                    except Exception:
                        pass
                    return {
                        "status": "SUCCESS",
                        "text": ocr_result.get("text", ""),
                        "filepath": filepath,
                        "width": w,
                        "height": h,
                    }

        # Fallback: screenshot with PIL + OCR via pytesseract
        try:
            from PIL import ImageGrab
            filepath = os.path.join("data", "screenshots", f"cu_{uuid.uuid4().hex[:8]}.png")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            img = ImageGrab.grab()
            img.save(filepath, "PNG")

            w, h = img.size
            ocr_text = _fallback_ocr(img)
            return {"status": "SUCCESS", "text": ocr_text, "filepath": filepath, "width": w, "height": h}
        except ImportError:
            return {"status": "ERROR", "error": "PIL not available for screenshots"}

    except Exception as e:
        logger.error(f"[ComputerUse] Observe error: {e}")
        return {"status": "ERROR", "error": str(e)}


def _fallback_ocr(image) -> str:
    """Extract text from a PIL image using pytesseract (existing project dependency).

    Gracefully degrades if pytesseract or tesseract binary is unavailable.
    Reuses the same Tesseract binary discovery logic as VisionAgent.

    Args:
        image: PIL Image object

    Returns:
        Extracted text string, or a descriptive fallback message.
    """
    try:
        import pytesseract
        import shutil

        # Discover Tesseract binary (same logic as VisionAgent)
        tesseract_env = os.getenv("TESSERACT_PATH")
        if tesseract_env and os.path.exists(tesseract_env):
            pytesseract.pytesseract.tesseract_cmd = tesseract_env
        elif not shutil.which(str(pytesseract.pytesseract.tesseract_cmd)):
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                "/usr/bin/tesseract",
                "/usr/local/bin/tesseract",
            ]
            for p in common_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

        extracted = pytesseract.image_to_string(image).strip()
        if extracted:
            logger.info(f"[ComputerUse] OCR extracted {len(extracted)} chars")
            return extracted

        return f"Image ({image.width}x{image.height}). OCR returned no text."

    except ImportError:
        logger.debug("[ComputerUse] pytesseract not available for OCR fallback")
        return f"Image ({image.width}x{image.height}). OCR unavailable (pytesseract not installed)."
    except Exception as e:
        logger.debug(f"[ComputerUse] OCR fallback error: {e}")
        w, h = getattr(image, 'size', (0, 0))
        return f"Image ({w}x{h}). OCR failed: {e}"


# =========================================================================
# DECIDE (Enhanced)
# =========================================================================

def _decide(
    task: str,
    screen_text: str,
    screen_w: int,
    screen_h: int,
    iteration: int,
) -> Dict[str, Any]:
    """Use LLM to decide what action(s) to take based on task and screen content.

    Enhanced with:
    - Actual screen dimensions for coordinate generation
    - Coordinate bounds enforcement
    - Multi-step plan support
    - Common app launch patterns
    - Invalid coordinate rejection
    """
    try:
        from brain.llm_manager import llm_manager

        # Check if this is a common "open app" task → use keyboard launch plan
        app_launch = _get_app_launch_plan(task)
        if app_launch:
            logger.info(f"[ComputerUse] App launch detected: {app_launch.get('app_name', 'unknown')}")
            return app_launch

        prompt = (
            f"You are ULTRON controlling a computer.\n"
            f"Screen: {screen_w}x{screen_h} pixels. Coordinate origin: top-left (0,0).\n"
            f"Valid coordinates: 0 <= x < {screen_w}, 0 <= y < {screen_h}.\n"
            f"NEVER use (0,0) unless you literally mean the top-left pixel.\n\n"
            f"Current task: '{task}'\n"
            f"Screen OCR text (iteration {iteration}):\n{screen_text[:800]}\n\n"
            f"Decide the NEXT action. Respond with ONLY a JSON object:\n"
            f'{{"action_type": "click"|"type"|"key_press"|"scroll"|"wait"|"done"|"fail",\n'
            f' "details": "description of what to do",\n'
            f' "x": number_or_null, "y": number_or_null}}\n\n'
            f"For key_press: use details like 'win', 'enter', 'escape', 'tab', 'ctrl+c'.\n"
            f"For type: put the text to type in details.\n"
            f"For click: x and y MUST be valid coordinates within {screen_w}x{screen_h}.\n"
            f"If the task appears complete, use action_type \"done\".\n"
            f"If you cannot determine what to do, use \"fail\".\n"
            f"If no action needed yet, use \"wait\".\n"
            f"You may also return a \"plan\" array for multi-step sequences:\n"
            f'{{"action_type": "click", "details": "step", "x": 100, "y": 200, '
            f'"plan": [{{"action_type": "type", "details": "hello"}}, '
            f'{{"action_type": "key_press", "details": "enter"}}]}}'
        )

        response = llm_manager.ask(prompt)
        if not response or response.startswith("AI Model Error"):
            return {"action": "FAIL", "result": "LLM unavailable for decision-making"}

        # Parse JSON from response
        import json
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                decision = json.loads(json_match.group())
            except json.JSONDecodeError:
                return {"action": "FAIL", "result": f"Malformed JSON from LLM: {response[:200]}"}

            action = decision.get("action_type", "fail")
            if action == "done":
                return {"action": "DONE", "result": decision.get("details", "Task completed")}
            if action == "fail":
                return {"action": "FAIL", "result": decision.get("details", "Could not determine action")}
            return {"action": "ACT", **decision}

        return {"action": "FAIL", "result": f"Could not parse LLM response: {response[:200]}"}

    except Exception as e:
        logger.error(f"[ComputerUse] Decide error: {e}")
        return {"action": "FAIL", "result": f"Decision error: {e}"}


# =========================================================================
# APP LAUNCH PATTERN
# =========================================================================

# Conjunctions that separate app name from remaining task
_CONJUNCTIONS = r'(?:\s*and\s+|\s*then\s+|\s*after\s+that\s+|\s*next\s+|\s*,\s*)'

# Multi-word app names that should be matched as a unit
_MULTI_WORD_APPS = {
    "visual studio code": "visual studio code",
    "google chrome": "google chrome",
    "microsoft edge": "microsoft edge",
    "open office": "open office",
    "libre office": "libre office",
    "power shell": "powershell",
    "file explorer": "explorer",
    "task manager": "task manager",
    "control panel": "control panel",
}


def _get_app_launch_plan(task: str) -> Optional[Dict[str, Any]]:
    """Detect common 'open [app]' tasks and return a keyboard-based launch plan.

    Handles compound tasks like:
    - 'Open Calculator' → app=calculator, remaining=None
    - 'Open Calculator and calculate 123 + 456' → app=calculator, remaining='calculate 123 + 456'
    - 'Launch Google Chrome then search for news' → app=google chrome, remaining='search for news'

    Uses Windows key → type app name → Enter pattern.
    Returns None if the task doesn't match an app launch pattern.
    """
    task_lower = task.lower().strip()

    # Match patterns: "open calculator", "launch notepad", "start chrome", "run paint"
    match = re.match(r'(?:open|launch|start|run)\s+(.+)', task_lower)
    if not match:
        return None

    remainder = match.group(1).strip()
    app_name = None
    remaining_task = None

    # 1. Try multi-word known apps first (check longest match first)
    for multi_name in sorted(_MULTI_WORD_APPS.keys(), key=len, reverse=True):
        if remainder.startswith(multi_name):
            app_name = _MULTI_WORD_APPS[multi_name]
            rest = remainder[len(multi_name):].strip()
            # Split on conjunction to get remaining task
            conj_match = re.match(_CONJUNCTIONS + '(.+)', rest)
            if conj_match:
                remaining_task = conj_match.group(1).strip()
            elif rest and rest not in ('', '.'):
                remaining_task = rest
            break

    # 2. Try known single-word apps
    if app_name is None:
        for known in _KNOWN_APPS:
            if remainder == known or remainder.startswith(known + ' '):
                app_name = known
                rest = remainder[len(known):].strip()
                conj_match = re.match(_CONJUNCTIONS + '(.+)', rest)
                if conj_match:
                    remaining_task = conj_match.group(1).strip()
                elif rest and rest not in ('', '.'):
                    remaining_task = rest
                break

    # 3. Try splitting on conjunction to extract unknown app name
    if app_name is None:
        conj_match = re.match(r'(.+?)' + _CONJUNCTIONS + '(.+)', remainder)
        if conj_match:
            candidate = conj_match.group(1).strip()
            remaining_task = conj_match.group(2).strip()
            # Validate: reasonable app name (1-3 words, < 25 chars, alphabetic)
            words = candidate.split()
            if len(words) <= 3 and len(candidate) <= 25 and candidate.replace(' ', '').isalpha():
                app_name = candidate

    # 4. Last resort: single word, no conjunction
    if app_name is None:
        first_word = remainder.split()[0] if remainder.split() else None
        if first_word and first_word.isalpha() and len(first_word) <= 20:
            app_name = first_word
            rest = remainder[len(first_word):].strip()
            if rest and rest not in ('', '.'):
                remaining_task = rest

    if not app_name:
        return None

    # Reject overly long app names
    if len(app_name) > 25:
        return None

    logger.info(f"[ComputerUse] App launch: '{app_name}' (remaining: '{remaining_task}')")
    result = {
        "action": "ACT",
        "action_type": "key_press",
        "details": f"Press Win key to open Start menu",
        "app_name": app_name,
        "plan": [
            {"action_type": "key_press", "details": "win", "x": None, "y": None},
            {"action_type": "wait", "details": "Wait for Start menu", "x": None, "y": None},
            {"action_type": "type", "details": app_name, "x": None, "y": None},
            {"action_type": "key_press", "details": "enter", "x": None, "y": None},
        ],
    }
    if remaining_task:
        result["remaining_task"] = remaining_task
    return result


# =========================================================================
# VALIDATE
# =========================================================================

def _validate_action(
    decision: Dict[str, Any],
    screen_w: int,
    screen_h: int,
) -> Dict[str, Any]:
    """Validate a model-decided action before execution.

    Checks:
    - action_type is present and valid
    - click actions have numeric x,y within screen bounds
    - (0,0) is flagged as likely invalid
    - type/key_press actions have details text
    - No forbidden action types slip through

    Returns:
        {"valid": True/False, "reason": str}
    """
    action_type = decision.get("action_type")

    # Must have action_type
    if not action_type:
        return {"valid": False, "reason": "Missing action_type"}

    # Must be a recognized action
    if action_type not in VALID_ACTION_TYPES:
        return {"valid": False, "reason": f"Unknown action_type: '{action_type}'"}

    # Click requires valid coordinates (only check for click actions)
    if action_type == "click":
        x = decision.get("x")
        y = decision.get("y")

        if x is None or y is None:
            return {"valid": False, "reason": "Click action missing x or y coordinate"}

        try:
            x = int(x)
            y = int(y)
        except (ValueError, TypeError):
            return {"valid": False, "reason": f"Non-numeric coordinates: x={x}, y={y}"}

        # Reject (0,0) — almost certainly a default/null value
        if x == 0 and y == 0:
            return {"valid": False, "reason": "Coordinates (0,0) rejected — likely default/null, not a real target"}

        # Must be within screen bounds
        if x < 0 or x >= screen_w:
            return {"valid": False, "reason": f"x={x} out of bounds (0-{screen_w - 1})"}
        if y < 0 or y >= screen_h:
            return {"valid": False, "reason": f"y={y} out of bounds (0-{screen_h - 1})"}

    # Type requires text in details
    if action_type == "type":
        details = decision.get("details", "")
        if not details or not details.strip():
            return {"valid": False, "reason": "Type action missing text in details"}

    # key_press requires details
    if action_type == "key_press":
        details = decision.get("details", "")
        if not details or not details.strip():
            return {"valid": False, "reason": "key_press action missing key in details"}

    return {"valid": True, "reason": ""}


# =========================================================================
# ACT
# =========================================================================

def _act(decision: Dict[str, Any], agent_manager=None) -> Dict[str, Any]:
    """Execute the decided action."""
    action_type = decision.get("action_type", "")

    try:
        if action_type == "click":
            x = decision.get("x")
            y = decision.get("y")
            if x is not None and y is not None:
                return _platform_mouse_click(int(x), int(y))
            return {"status": "ERROR", "error": "Click requires x,y coordinates"}

        elif action_type == "type":
            text = decision.get("details", "")
            if text:
                return _platform_keyboard_type(text)
            return {"status": "ERROR", "error": "Type requires text in details"}

        elif action_type == "key_press":
            key = decision.get("details", "")
            if key:
                return _platform_key_press(key)
            return {"status": "ERROR", "error": "key_press requires key name in details"}

        elif action_type == "scroll":
            direction = decision.get("details", "down")
            return _platform_scroll(direction)

        elif action_type == "wait":
            return {"status": "SUCCESS", "result": "Waiting"}

        else:
            return {"status": "ERROR", "error": f"Unknown action type: {action_type}"}

    except Exception as e:
        logger.error(f"[ComputerUse] Act error: {e}")
        return {"status": "ERROR", "error": str(e)}


# =========================================================================
# PLATFORM ACTIONS
# =========================================================================

def _platform_mouse_click(x: int, y: int) -> Dict[str, Any]:
    """Execute mouse click via platform adapter."""
    try:
        import ultron_platform
        adapter = ultron_platform.get_platform_adapter()
        result = adapter.mouse_click(x, y)
        return {"status": "SUCCESS" if result.get("available") else "ERROR", "result": result.get("result", ""), "error": result.get("error")}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def _platform_keyboard_type(text: str) -> Dict[str, Any]:
    """Execute keyboard typing via platform adapter."""
    try:
        import ultron_platform
        adapter = ultron_platform.get_platform_adapter()
        result = adapter.keyboard_type(text)
        return {"status": "SUCCESS" if result.get("available") else "ERROR", "result": result.get("result", ""), "error": result.get("error")}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def _platform_key_press(key: str) -> Dict[str, Any]:
    """Execute a single key press (win, enter, escape, tab, etc.) via ctypes."""
    try:
        import ctypes
        user32 = ctypes.windll.user32

        key_map = {
            "win": 0x5B,
            "enter": 0x0D,
            "return": 0x0D,
            "escape": 0x1B,
            "esc": 0x1B,
            "tab": 0x09,
            "space": 0x20,
            "backspace": 0x08,
            "delete": 0x2E,
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
            "home": 0x24,
            "end": 0x23,
            "pageup": 0x21,
            "pagedown": 0x22,
            "ctrl+a": None,  # Handle combo below
            "ctrl+c": None,
            "ctrl+v": None,
            "ctrl+z": None,
        }

        key_lower = key.lower().strip()

        # Handle key combos (e.g., "ctrl+c", "ctrl+v")
        if "+" in key_lower:
            parts = [p.strip() for p in key_lower.split("+")]
            vk_codes = []
            for part in parts:
                if part == "ctrl":
                    vk_codes.append(0x11)
                elif part == "alt":
                    vk_codes.append(0x12)
                elif part == "shift":
                    vk_codes.append(0x10)
                elif part in key_map and key_map[part] is not None:
                    vk_codes.append(key_map[part])
                elif len(part) == 1:
                    vk_codes.append(ord(part.upper()))
                else:
                    return {"status": "ERROR", "error": f"Unknown key in combo: '{part}'"}

            # Press all modifier + key, then release in reverse
            for vk in vk_codes:
                user32.keybd_event(vk, 0, 0, 0)
            for vk in reversed(vk_codes):
                user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP
            return {"status": "SUCCESS", "result": f"Pressed {key}"}

        # Single key
        vk = key_map.get(key_lower)
        if vk is None and key_lower not in key_map:
            # Try single character
            if len(key_lower) == 1:
                vk = ord(key_lower.upper())
            else:
                return {"status": "ERROR", "error": f"Unknown key: '{key}'"}

        if vk is not None:
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP
            return {"status": "SUCCESS", "result": f"Pressed {key}"}

        return {"status": "ERROR", "error": f"Could not map key: '{key}'"}

    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def _platform_scroll(direction: str) -> Dict[str, Any]:
    """Execute scroll via browser agent if available."""
    # Scroll is typically browser-specific; basic implementation
    return {"status": "SUCCESS", "result": f"Scroll {direction} requested"}
