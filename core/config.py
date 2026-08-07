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


# Global Config Singleton
config = Config()
