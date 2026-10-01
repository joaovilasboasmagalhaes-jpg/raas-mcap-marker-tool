"""Small stdout/stderr logger used by the RaaS job utility."""

import enum
import os
import sys
from typing import Union


class LogLevel(enum.Enum):
    """Supported logging thresholds."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


CURRENT_LOG_LEVEL = LogLevel.INFO


def set_log_level(level: Union[LogLevel, str]) -> None:
    """Set the global log level threshold."""
    global CURRENT_LOG_LEVEL
    if isinstance(level, str):
        level_map = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "WARN": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
        }
        CURRENT_LOG_LEVEL = level_map.get(level.upper(), LogLevel.INFO)
    elif isinstance(level, LogLevel):
        CURRENT_LOG_LEVEL = level


def log_message(level: LogLevel, message: str) -> None:
    """Print a formatted message when it meets the current threshold."""
    if level.value < CURRENT_LOG_LEVEL.value:
        return

    prefix_map = {
        LogLevel.DEBUG: "[DEBUG]",
        LogLevel.INFO: "[INFO]",
        LogLevel.WARNING: "[WARNING]",
        LogLevel.ERROR: "[ERROR]",
    }
    prefix = prefix_map.get(level, "[INFO]")
    out_stream = sys.stderr if level == LogLevel.ERROR else sys.stdout
    formatted_message = f"{prefix} {message}"
    color_codes = {
        LogLevel.DEBUG: "\033[34m",
        LogLevel.WARNING: "\033[33m",
        LogLevel.ERROR: "\033[31m",
    }
    color_code = color_codes.get(level)
    if color_code and out_stream.isatty() and "NO_COLOR" not in os.environ:
        formatted_message = f"{color_code}{formatted_message}\033[0m"
    print(formatted_message, file=out_stream, flush=True)


def log_debug(message: str) -> None:
    """Log a debug message."""
    log_message(LogLevel.DEBUG, message)


def log_info(message: str) -> None:
    """Log an informational message."""
    log_message(LogLevel.INFO, message)


def log_warning(message: str) -> None:
    """Log a warning message."""
    log_message(LogLevel.WARNING, message)


def log_error(message: str) -> None:
    """Log an error message."""
    log_message(LogLevel.ERROR, message)
