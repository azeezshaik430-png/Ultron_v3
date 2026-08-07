"""
ULTRON V3 - Core Lifecycle Interfaces
Abstract base classes defining production service lifecycle contracts.
Zero external framework dependencies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class IService(ABC):
    """
    Base lifecycle contract for all production services in ULTRON V3.
    
    Responsibilities:
    - Defines universal initialization, shutdown, health check, and configuration contracts.
    
    Thread-Safety:
    - Implementations must guarantee thread-safe state transitions.
    """

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the service resources and prepare for execution.
        
        Raises:
            BusException: If initialization fails.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Cleanly release all service resources, background threads, and file handles.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Return service health telemetry status.
        
        Returns:
            Dict[str, Any]: Health status dictionary containing 'status', 'healthy', and metrics.
        """
        pass

    @abstractmethod
    def configure(self, config_data: Dict[str, Any]) -> None:
        """
        Apply configuration settings to the service.
        
        Args:
            config_data (Dict[str, Any]): Dictionary of configuration keys and values.
        """
        pass


class IInitializable(IService, ABC):
    """Explicit initializable service sub-interface."""
    pass


class IShutdownable(IService, ABC):
    """Explicit shutdownable service sub-interface."""
    pass


class IHealthCheck(IService, ABC):
    """Explicit health check service sub-interface."""
    pass


class IConfigurable(IService, ABC):
    """Explicit configurable service sub-interface."""
    pass
