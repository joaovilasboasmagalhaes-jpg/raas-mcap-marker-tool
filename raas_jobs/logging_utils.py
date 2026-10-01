"""Small stdout/stderr logger used by the RaaS job utility."""

import datetime
import enum
import os
import sys
from typing import IO, Optional, Union


class LogLevel(enum.Enum):
    """Supported logging thresholds."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


CURRENT_LOG_LEVEL = LogLevel.INFO
_LOG_FILE_HANDLE: Optional[IO[str]] = None


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


def configure_log_file(path: str) -> str:
    """Open `path` for appending so all subsequent log messages are also recorded there."""
    global _LOG_FILE_HANDLE
    close_log_file()
    resolved_path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(resolved_path) or ".", exist_ok=True)
    _LOG_FILE_HANDLE = open(resolved_path, "a", encoding="utf-8")
    return resolved_path


def close_log_file() -> None:
    """Close the current log file, if one is open."""
    global _LOG_FILE_HANDLE
    if _LOG_FILE_HANDLE is not None:
        _LOG_FILE_HANDLE.close()
        _LOG_FILE_HANDLE = None


def write_raw(line: str, out_stream: IO[str] = sys.stdout) -> None:
    """Echo a pre-formatted line (e.g. subprocess output) to the terminal and log file."""
    print(line, file=out_stream, end="", flush=True)
    if _LOG_FILE_HANDLE is not None:
        _LOG_FILE_HANDLE.write(line)
        _LOG_FILE_HANDLE.flush()


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

    if _LOG_FILE_HANDLE is not None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _LOG_FILE_HANDLE.write(f"{timestamp} {formatted_message}\n")
        _LOG_FILE_HANDLE.flush()

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
