"""
ULTRON V3 - Core Logger
UTF-8 safe, lightweight rotating file and console logger.
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from core.config import config


def setup_logger(name: str = "ULTRON") -> logging.Logger:
    """Configure and return the master ULTRON logger."""
    log = logging.getLogger(name)
    
    if log.handlers:
        return log

    level = logging.DEBUG if config.DEBUG else logging.INFO
    log.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. UTF-8 Safe Rotating File Handler
    log_path = config.get_log_path()
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    # 2. UTF-8 Safe Console Stream Handler
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    return log


# Global Logger Singleton
logger = setup_logger()
