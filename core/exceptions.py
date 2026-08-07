"""
ULTRON V3 - Core Exception Taxonomy
Domain exception classes for the Agent Memory Bus and system subsystems.
Zero external framework dependencies.
"""


class BusException(Exception):
    """
    Base domain exception for all Agent Memory Bus errors.
    
    Purpose:
    - Provides a unified parent exception class for bus runtime errors.
    
    Thread-Safety:
    - Immutable exception instance.
    """
    pass


class AgentNotFoundException(BusException):
    """Raised when an operation targets an unregistered or non-existent subagent."""
    pass


class DuplicateMessageException(BusException):
    """Raised when a message payload with a duplicate hash is detected."""
    pass


class QuotaExceededException(BusException):
    """Raised when an agent, task, or workspace memory quota is exceeded."""
    pass


class PermissionDeniedException(BusException):
    """Raised when an agent violates workspace ACL access controls."""
    pass


class WorkspaceConflictException(BusException):
    """Raised when an optimistic workspace version check fails during commit."""
    pass


class JournalCorruptionException(BusException):
    """Raised when state journal or snapshot integrity verification fails."""
    pass
