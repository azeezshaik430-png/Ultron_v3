"""
ULTRON V3 - Configuration Validation Engine
Schema, range, and type validation engine with severity classification and environment overrides.
Zero external framework dependencies.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from core.exceptions import BusException


class ValidationSeverity(str, Enum):
    """Configuration validation issue severity level."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


@dataclass
class ValidationEntry:
    """Individual configuration validation result entry."""
    field_name: str
    severity: ValidationSeverity
    message: str
    actual_value: Any = None


@dataclass
class ValidationReport:
    """Configuration validation report summary."""
    is_valid: bool = True
    has_fatal: bool = False
    entries: List[ValidationEntry] = field(default_factory=list)

    def add_entry(self, field_name: str, severity: ValidationSeverity, message: str, actual_value: Any = None) -> None:
        """Add a validation result entry to the report."""
        entry = ValidationEntry(
            field_name=field_name,
            severity=severity,
            message=message,
            actual_value=actual_value,
        )
        self.entries.append(entry)
        if severity == ValidationSeverity.FATAL:
            self.is_valid = False
            self.has_fatal = True
        elif severity == ValidationSeverity.ERROR:
            self.is_valid = False


class ConfigValidator:
    """
    Configuration Validation Engine.
    
    Purpose:
    - Inspects configuration parameters for type safety, numerical range compliance, and environment overrides.
    
    Responsibilities:
    - Resolves environment variable overrides (`ULTRON_CONFIG_*`).
    - Classifies configuration issues into INFO, WARNING, ERROR, or FATAL.
    - Aborts system boot if FATAL issues are encountered.
    
    Thread-Safety:
    - Read-only validation operations on configuration instances.
    """

    def __init__(self) -> None:
        self._last_report: Optional[ValidationReport] = None

    def validate(self, config_obj: Any) -> ValidationReport:
        """
        Validate a configuration dataclass instance.
        
        Args:
            config_obj (Any): Dataclass configuration object to validate.
            
        Returns:
            ValidationReport: Validation summary report.
            
        Raises:
            BusException: If FATAL severity configuration errors are found.
        """
        report = ValidationReport()

        # 1. Resolve environment variable overrides
        self._apply_env_overrides(config_obj, report)

        # 2. Type & Range Validations
        self._validate_numerical_ranges(config_obj, report)
        self._validate_string_paths(config_obj, report)

        self._last_report = report

        # 3. Handle FATAL severity
        if report.has_fatal:
            fatal_msgs = [f"{e.field_name}: {e.message}" for e in report.entries if e.severity == ValidationSeverity.FATAL]
            raise BusException(f"FATAL Configuration Error(s): {'; '.join(fatal_msgs)}")

        return report

    def get_report(self) -> Optional[ValidationReport]:
        """Return the last generated validation report."""
        return self._last_report

    def _apply_env_overrides(self, config_obj: Any, report: ValidationReport) -> None:
        """Scan process environment for ULTRON_CONFIG_* overrides."""
        prefix = "ULTRON_CONFIG_"
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                attr_name = env_key[len(prefix):]
                if hasattr(config_obj, attr_name):
                    orig_val = getattr(config_obj, attr_name)
                    parsed_val = self._parse_env_type(env_val, type(orig_val))
                    setattr(config_obj, attr_name, parsed_val)
                    report.add_entry(
                        field_name=attr_name,
                        severity=ValidationSeverity.INFO,
                        message=f"Applied environment override: '{env_key}' -> '{parsed_val}'",
                        actual_value=parsed_val,
                    )

    def _parse_env_type(self, val_str: str, target_type: type) -> Any:
        """Parse string environment value to target attribute type."""
        if target_type is bool:
            return val_str.lower() in ("true", "1", "yes", "on")
        if target_type is int:
            try:
                return int(val_str)
            except ValueError:
                return val_str
        if target_type is float:
            try:
                return float(val_str)
            except ValueError:
                return val_str
        return val_str

    def _validate_numerical_ranges(self, config_obj: Any, report: ValidationReport) -> None:
        """Validate numeric configuration attributes against safety bounds."""
        # Worker Count Range
        if hasattr(config_obj, "TASK_ENGINE_WORKER_COUNT"):
            val = getattr(config_obj, "TASK_ENGINE_WORKER_COUNT")
            if not isinstance(val, int):
                report.add_entry("TASK_ENGINE_WORKER_COUNT", ValidationSeverity.FATAL, "Must be an integer.", val)
            elif val < 1:
                report.add_entry("TASK_ENGINE_WORKER_COUNT", ValidationSeverity.FATAL, "Worker count must be >= 1.", val)
            elif val > 32:
                report.add_entry("TASK_ENGINE_WORKER_COUNT", ValidationSeverity.WARNING, "Worker count > 32 may cause thread contention.", val)

        # Queue Max Size
        if hasattr(config_obj, "TASK_ENGINE_QUEUE_MAX_SIZE"):
            val = getattr(config_obj, "TASK_ENGINE_QUEUE_MAX_SIZE")
            if not isinstance(val, int):
                report.add_entry("TASK_ENGINE_QUEUE_MAX_SIZE", ValidationSeverity.FATAL, "Must be an integer.", val)
            elif val < 10:
                report.add_entry("TASK_ENGINE_QUEUE_MAX_SIZE", ValidationSeverity.FATAL, "Queue size must be >= 10.", val)

        # Lease Timeout
        if hasattr(config_obj, "TASK_ENGINE_LEASE_TIMEOUT"):
            val = getattr(config_obj, "TASK_ENGINE_LEASE_TIMEOUT")
            if not isinstance(val, (int, float)) or val <= 0:
                report.add_entry("TASK_ENGINE_LEASE_TIMEOUT", ValidationSeverity.FATAL, "Lease timeout must be > 0.", val)

    def _validate_string_paths(self, config_obj: Any, report: ValidationReport) -> None:
        """Validate string path settings."""
        if hasattr(config_obj, "BASE_DIR"):
            val = getattr(config_obj, "BASE_DIR")
            if not isinstance(val, str) or not val.strip():
                report.add_entry("BASE_DIR", ValidationSeverity.FATAL, "BASE_DIR cannot be empty.", val)
