"""
ULTRON V3 - Task Planner
Simple command direct execution vs complex subtask planning framework.
"""

from typing import Dict, Any, List


def plan(intent_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Planner receives parsed intent and produces execution plan.
    Phase 1: Simple single-step direct execution.
    """
    intent = intent_data.get("intent", "UNKNOWN")
    target = intent_data.get("target", "")

    # Identify simple vs complex
    is_complex = intent_data.get("is_complex", False)

    steps: List[Dict[str, Any]] = [
        {
            "action": intent,
            "target": target
        }
    ]

    return {
        "status": "READY",
        "intent": intent,
        "target": target,
        "is_complex": is_complex,
        "steps": steps
    }