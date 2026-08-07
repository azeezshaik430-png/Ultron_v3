"""
ULTRON V3 - Temporary Command Handler Wrapper
Temporary migration wrapper forwarding calls to central Orchestrator.
Maintained ONLY for backward compatibility during Phase 1 migration.
"""

from brain.orchestrator import orchestrator


def handle_command(command: str) -> str:
    """Forward command to central Orchestrator controller."""
    return orchestrator.process_command(command)