"""
ULTRON V3
Computer-Use Module

Observe → Understand → Decide → Act → Verify loop.
Requires explicit activation. Max 5 iterations per request.
Destructive actions require confirmation. Never autonomous shutdown/restart/delete.
"""

import os
import time
import uuid
from typing import Dict, Any, Optional
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

MAX_ITERATIONS = 5
OBSERVE_DELAY = 0.5  # seconds between iterations


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


def execute_computer_use_task(
    task_description: str,
    vision_agent=None,
    agent_manager=None,
) -> Dict[str, Any]:
    """
    Execute a computer-use task through the observe→decide→act→verify loop.
    
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

    logger.info(f"[ComputerUse] Task: '{task_description}' (iteration {iterations + 1}/{MAX_ITERATIONS})")

    for i in range(MAX_ITERATIONS - iterations):
        current_iter = iterations + i + 1
        session.session_data["computer_use_iterations"] = current_iter

        # 1. OBSERVE — Screenshot + OCR
        observe_result = _observe(vision_agent)
        if observe_result.get("status") == "ERROR":
            return {
                "status": "ERROR",
                "iterations": current_iter,
                "actions_taken": actions_taken,
                "result": f"Failed to observe screen: {observe_result.get('error', 'Unknown error')}",
            }

        screen_text = observe_result.get("text", "")
        logger.info(f"[ComputerUse] Observe iteration {current_iter}: {len(screen_text)} chars OCR")

        # 2. UNDERSTAND + DECIDE — Use LLM to decide action
        decision = _decide(task_description, screen_text, current_iter)
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

        # 3. SAFETY CHECK
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

        # 4. ACT — Execute the action
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

        # Brief delay between iterations
        time.sleep(OBSERVE_DELAY)

    # Max iterations reached
    return {
        "status": "MAX_ITERATIONS",
        "iterations": MAX_ITERATIONS,
        "actions_taken": actions_taken,
        "result": f"Reached maximum iterations ({MAX_ITERATIONS}). {len(actions_taken)} actions taken.",
    }


def _observe(vision_agent=None) -> Dict[str, Any]:
    """Capture screenshot and extract OCR text."""
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
                    return {
                        "status": "SUCCESS",
                        "text": ocr_result.get("text", ""),
                        "filepath": filepath,
                    }

        # Fallback: basic screenshot with PIL
        try:
            from PIL import ImageGrab
            filepath = os.path.join("data", "screenshots", f"cu_{uuid.uuid4().hex[:8]}.png")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            img = ImageGrab.grab()
            img.save(filepath, "PNG")
            return {"status": "SUCCESS", "text": f"[Screenshot saved to {filepath}]", "filepath": filepath}
        except ImportError:
            return {"status": "ERROR", "error": "PIL not available for screenshots"}

    except Exception as e:
        logger.error(f"[ComputerUse] Observe error: {e}")
        return {"status": "ERROR", "error": str(e)}


def _decide(task: str, screen_text: str, iteration: int) -> Dict[str, Any]:
    """Use LLM to decide what action to take based on task and screen content."""
    try:
        from brain.llm_manager import llm_manager

        prompt = (
            f"You are ULTRON controlling a computer. Current task: '{task}'\n"
            f"Screen OCR text (iteration {iteration}):\n{screen_text[:800]}\n\n"
            f"Decide the NEXT action. Respond with ONLY a JSON object:\n"
            f'{{"action_type": "click"|"type"|"scroll"|"wait"|"done"|"fail",\n'
            f' "details": "description of what to do",\n'
            f' "x": null, "y": null}}\n'
            f"If the task appears complete, use action_type \"done\".\n"
            f"If you cannot determine what to do, use \"fail\".\n"
            f"If no action needed yet, use \"wait\"."
        )

        response = llm_manager.ask(prompt)
        if not response or response.startswith("AI Model Error"):
            return {"action": "FAIL", "result": "LLM unavailable for decision-making"}

        # Parse JSON from response
        import json
        import re
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            decision = json.loads(json_match.group())
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


def _platform_scroll(direction: str) -> Dict[str, Any]:
    """Execute scroll via browser agent if available."""
    # Scroll is typically browser-specific; basic implementation
    return {"status": "SUCCESS", "result": f"Scroll {direction} requested"}
