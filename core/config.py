"""
ULTRON V3 - Core Configuration
Lightweight dataclass configuration system.
Zero external framework dependencies.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Config:
    """Central configuration parameters for ULTRON V3."""

    # Assistant Identity
    ASSISTANT_NAME: str = "Ultron"
    OWNER_NAME: str = "Boss"
    VERSION: str = "3.0"
    DANGEROUS_COMMANDS_ENABLED: bool = False

    # AI Model Settings
    DEFAULT_LLM_PROVIDER: str = "ollama"
    OLLAMA_MODEL: str = "llama3.2:3b"

    # Audio & Voice Settings
    VOICE_RATE: int = 220
    VOICE_VOLUME: float = 1.0
    WAKE_WORD: str = "ultron"
    LANGUAGE: str = "en"
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_RECORD_DURATION: int = 5
    VOICE_AUTH_ENABLED: bool = field(
        default_factory=lambda: os.getenv("VOICE_AUTH_ENABLED", "true").lower() in ["true", "1", "yes"]
    )

    # Path Settings
    BASE_DIR: str = field(
        default_factory=lambda: os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
    DATA_DIR: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
    )
    LOGS_DIR: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
    )
    MEMORY_DIR: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory"
        )
    )

    # Logging Settings
    DEBUG: bool = True
    LOG_FILE_NAME: str = "ultron.log"
    LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
    LOG_BACKUP_COUNT: int = 3

    def get_data_path(self, filename: str) -> str:
        """Return absolute path for a data file."""
        return os.path.join(self.DATA_DIR, filename)

    def get_log_path(self) -> str:
        """Return absolute path for master log file."""
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        return os.path.join(self.LOGS_DIR, self.LOG_FILE_NAME)


    # Task Engine Settings
    TASK_ENGINE_WORKER_COUNT: int = 4
    TASK_ENGINE_QUEUE_MAX_SIZE: int = 1000
    TASK_ENGINE_MAX_RETRIES: int = 3
    TASK_ENGINE_LEASE_TIMEOUT: float = 30.0
    TASK_ENGINE_WATCHDOG_INTERVAL: float = 2.0
    TASK_ENGINE_BASE_RETRY_DELAY: float = 1.0

    # Agent Memory Bus Settings
    AGENT_BUS_VERSION: int = 1
    FEATURE_FLAGS_VERSION: int = 1
    AGENT_BUS_DEFAULT_TTL_MS: int = 30000
    AGENT_BUS_MAX_QUEUE_SIZE: int = 500
    AGENT_BUS_ARTIFACTS_DIR: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "artifacts"
        )
    )

    # Health Monitor Settings
    HEALTH_MONITOR_INSPECTION_INTERVAL: float = 5.0
    HEALTH_MONITOR_HEARTBEAT_TIMEOUT: float = 15.0
    HEALTH_MONITOR_FAILURE_THRESHOLD: int = 3

    # Workspace Store & Transaction Settings
    WORKSPACE_MAX_SIZE_MB: int = 25
    WORKSPACE_TRANSACTION_TIMEOUT: float = 10.0
    WORKSPACE_SNAPSHOT_INTERVAL: float = 30.0
    WORKSPACE_MAX_VERSIONS: int = 50
    WORKSPACE_MAX_KEYS: int = 1000
    WORKSPACE_MAX_VALUE_SIZE: int = 5 * 1024 * 1024  # 5 MB
    WORKSPACE_MAX_SNAPSHOTS: int = 10

    # Message Router, Scratchpad & Artifact Settings
    MESSAGE_ROUTER_MAX_RETRIES: int = 3
    MESSAGE_ROUTER_DEFAULT_TTL_MS: int = 30000
    MESSAGE_ROUTER_BACKOFF_BASE: float = 0.1
    SCRATCHPAD_MAX_SIZE_MB: int = 10
    ARTIFACT_MAX_STORAGE_MB: int = 2000

    # Recovery Journal, Garbage Collector & Metrics Settings
    RECOVERY_JOURNAL_PATH: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bus_journal.log"
        )
    )
    RECOVERY_CHECKPOINT_INTERVAL: float = 60.0
    GC_INTERVAL: float = 30.0
    GC_MAX_BATCH: int = 500
    METRICS_EXPORT_INTERVAL: float = 5.0

    # Service Manager Settings
    SERVICE_STARTUP_TIMEOUT: float = 10.0
    SERVICE_SHUTDOWN_TIMEOUT: float = 10.0
    SERVICE_HEALTH_INTERVAL: float = 5.0

    # Phase 2B Agent Manager Settings
    AGENT_MANAGER_VERSION: int = 1
    AGENT_EXECUTION_TIMEOUT: float = 30.0
    SYSTEM_AGENT_ENABLED: bool = True
    MEMORY_AGENT_ENABLED: bool = True
    TASK_AGENT_ENABLED: bool = True
    PLANNING_AGENT_ENABLED: bool = True
    RESEARCH_AGENT_ENABLED: bool = True
    CODING_AGENT_ENABLED: bool = True
    VISION_AGENT_ENABLED: bool = True
    BROWSER_AGENT_ENABLED: bool = True


# Instantiated global singleton
config = Config()
