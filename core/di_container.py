"""
ULTRON V3 - Core Dependency Injection Container
Thread-safe dependency injection container supporting Singleton, Factory, Lazy, and Transient services,
circular dependency detection, and startup validation.
Zero external framework dependencies.
"""

import threading
from typing import Dict, Any, Type, Callable, Optional, Set, List
from core.exceptions import BusException


class RegistrationType:
    """Service registration lifetime type enum."""
    SINGLETON = "SINGLETON"
    FACTORY = "FACTORY"
    LAZY = "LAZY"
    TRANSIENT = "TRANSIENT"


class ServiceEntry:
    """Container internal registration metadata wrapper."""

    def __init__(
        self,
        service_type: Type,
        reg_type: str,
        instance: Optional[Any] = None,
        factory: Optional[Callable[[], Any]] = None,
        dependencies: Optional[List[Type]] = None,
    ) -> None:
        self.service_type = service_type
        self.reg_type = reg_type
        self.instance = instance
        self.factory = factory
        self.dependencies = dependencies or []


class DIContainer:
    """
    Thread-safe Dependency Injection Container.
    
    Purpose:
    - Centralizes service creation, lifecycle management, and dependency resolution.
    
    Responsibilities:
    - Registers Singleton, Factory, Lazy, and Transient services.
    - Resolves service instances on demand with circular dependency protection.
    - Validates service dependency graphs prior to application startup.
    
    Thread-Safety:
    - All registration, resolution, replacement, and validation calls are protected by an RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._services: Dict[Type, ServiceEntry] = {}
        self._resolving_stack: Set[Type] = set()

    def register_singleton(self, service_type: Type, instance: Any) -> None:
        """
        Register a pre-instantiated singleton service.
        
        Args:
            service_type (Type): Target service interface or class type.
            instance (Any): Pre-constructed object instance.
            
        Raises:
            BusException: If instance is None.
        """
        if instance is None:
            raise BusException("Singleton instance cannot be None.")

        with self._lock:
            self._services[service_type] = ServiceEntry(
                service_type=service_type,
                reg_type=RegistrationType.SINGLETON,
                instance=instance,
            )

    def register_factory(
        self,
        service_type: Type,
        factory_func: Callable[[], Any],
        dependencies: Optional[List[Type]] = None,
    ) -> None:
        """
        Register a factory function producing new instances on every resolve call.
        
        Args:
            service_type (Type): Target service interface or class type.
            factory_func (Callable[[], Any]): Callable returning a new service instance.
            dependencies (Optional[List[Type]]): Optional list of dependent service types.
        """
        if not callable(factory_func):
            raise BusException("Factory function must be callable.")

        with self._lock:
            self._services[service_type] = ServiceEntry(
                service_type=service_type,
                reg_type=RegistrationType.FACTORY,
                factory=factory_func,
                dependencies=dependencies,
            )

    def register_lazy(
        self,
        service_type: Type,
        factory_func: Callable[[], Any],
        dependencies: Optional[List[Type]] = None,
    ) -> None:
        """
        Register a lazy-initialized singleton service constructed on first resolve.
        
        Args:
            service_type (Type): Target service interface or class type.
            factory_func (Callable[[], Any]): Callable returning a new singleton instance.
            dependencies (Optional[List[Type]]): Optional list of dependent service types.
        """
        if not callable(factory_func):
            raise BusException("Lazy factory function must be callable.")

        with self._lock:
            self._services[service_type] = ServiceEntry(
                service_type=service_type,
                reg_type=RegistrationType.LAZY,
                factory=factory_func,
                dependencies=dependencies,
            )

    def register_transient(
        self,
        service_type: Type,
        factory_func: Callable[[], Any],
        dependencies: Optional[List[Type]] = None,
    ) -> None:
        """
        Register a transient service factory evaluated on every request.
        
        Args:
            service_type (Type): Target service interface or class type.
            factory_func (Callable[[], Any]): Callable returning a new transient instance.
            dependencies (Optional[List[Type]]): Optional list of dependent service types.
        """
        if not callable(factory_func):
            raise BusException("Transient factory function must be callable.")

        with self._lock:
            self._services[service_type] = ServiceEntry(
                service_type=service_type,
                reg_type=RegistrationType.TRANSIENT,
                factory=factory_func,
                dependencies=dependencies,
            )

    def resolve(self, service_type: Type) -> Any:
        """
        Resolve and return an instance of the requested service type.
        
        Args:
            service_type (Type): Target service type.
            
        Returns:
            Any: Resolved service instance.
            
        Raises:
            BusException: If service is unregistered or circular dependency is detected.
        """
        with self._lock:
            if service_type in self._resolving_stack:
                raise BusException(f"Circular dependency detected for type: {service_type.__name__}")

            entry = self._services.get(service_type)
            if not entry:
                raise BusException(f"Service type '{service_type.__name__}' is not registered.")

            if entry.reg_type == RegistrationType.SINGLETON:
                return entry.instance

            if entry.reg_type == RegistrationType.LAZY:
                if entry.instance is None:
                    self._resolving_stack.add(service_type)
                    try:
                        entry.instance = entry.factory()
                    finally:
                        self._resolving_stack.remove(service_type)
                return entry.instance

            if entry.reg_type in [RegistrationType.FACTORY, RegistrationType.TRANSIENT]:
                self._resolving_stack.add(service_type)
                try:
                    instance = entry.factory()
                finally:
                    self._resolving_stack.remove(service_type)
                return instance

            raise BusException(f"Unknown registration type for '{service_type.__name__}'.")

    def validate_dependencies(self) -> Dict[str, Any]:
        """
        Validate the complete dependency graph prior to application boot.
        
        Returns:
            Dict[str, Any]: Summary dictionary with 'valid' bool, 'errors' list, and 'total_services' int.
            
        Raises:
            BusException: If fatal validation errors (missing or circular dependencies) exist.
        """
        with self._lock:
            errors: List[str] = []

            for stype, entry in list(self._services.items()):
                # Check for missing dependencies
                for dep_type in entry.dependencies:
                    if dep_type not in self._services:
                        errors.append(
                            f"Service '{stype.__name__}' has missing dependency: '{dep_type.__name__}'"
                        )

                # Check for invalid factories
                if entry.reg_type in [RegistrationType.FACTORY, RegistrationType.LAZY, RegistrationType.TRANSIENT]:
                    if not entry.factory or not callable(entry.factory):
                        errors.append(f"Service '{stype.__name__}' has an invalid or non-callable factory.")

                # Check circular dependencies via DFS
                try:
                    self._check_circular_dfs(stype, set())
                except BusException as ex:
                    errors.append(str(ex))

            is_valid = len(errors) == 0
            report = {
                "valid": is_valid,
                "errors": errors,
                "total_services": len(self._services),
            }

            if not is_valid:
                raise BusException(f"DI Container Validation Failed: {'; '.join(errors)}")

            return report

    def _check_circular_dfs(self, current: Type, visited: Set[Type]) -> None:
        """Internal DFS helper for circular dependency validation."""
        if current in visited:
            raise BusException(f"Circular dependency path detected involving: {current.__name__}")

        visited.add(current)
        entry = self._services.get(current)
        if entry:
            for dep in entry.dependencies:
                self._check_circular_dfs(dep, set(visited))

    def replace_service(self, service_type: Type, new_instance: Any) -> None:
        """
        Replace an existing registered service with a new singleton instance.
        
        Args:
            service_type (Type): Target service type.
            new_instance (Any): Replacement object instance.
        """
        if new_instance is None:
            raise BusException("Replacement instance cannot be None.")

        with self._lock:
            self._services[service_type] = ServiceEntry(
                service_type=service_type,
                reg_type=RegistrationType.SINGLETON,
                instance=new_instance,
            )

    def remove_service(self, service_type: Type) -> bool:
        """
        Remove a service registration from the container.
        
        Args:
            service_type (Type): Target service type.
            
        Returns:
            bool: True if removed, False if service was not present.
        """
        with self._lock:
            if service_type in self._services:
                del self._services[service_type]
                return True
            return False

    def has_service(self, service_type: Type) -> bool:
        """Check if a service type is registered."""
        with self._lock:
            return service_type in self._services

    def clear(self) -> None:
        """Clear all service registrations."""
        with self._lock:
            self._services.clear()
            self._resolving_stack.clear()
