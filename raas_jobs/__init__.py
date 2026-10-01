"""Utilities for querying RaaS jobs and preparing MCAP downloads."""

from .downloads import build_mcap_download_command
from .graphql_api import GRAPHQL_ENDPOINT, QUERY_RAAS_JOBS, query_raas_jobs
from .logging_utils import (
    LogLevel,
    log_debug,
    log_error,
    log_info,
    log_warning,
    set_log_level,
)
from .mcap import (
    MCAP_TIME_FORMAT,
    MCAP_TIMESTAMP_PATTERN,
    extract_mcap_file_list,
    extract_mcap_time_range,
    find_mcap_for_timestamp,
    find_mcaps_for_interval,
)
from .processing import (
    coalesce_intervals,
    plan_job_snipping_operations,
    process_all_jobs,
    process_job_markers,
)
from .scripts import execute_download_script, generate_download_script
from .timestamps import UTC_PLUS_2, convert_timestamp_to_utc

__all__ = [
    "CURRENT_LOG_LEVEL",
    "GRAPHQL_ENDPOINT",
    "MCAP_TIME_FORMAT",
    "MCAP_TIMESTAMP_PATTERN",
    "QUERY_RAAS_JOBS",
    "UTC_PLUS_2",
    "LogLevel",
    "build_mcap_download_command",
    "coalesce_intervals",
    "convert_timestamp_to_utc",
    "execute_download_script",
    "extract_mcap_file_list",
    "extract_mcap_time_range",
    "find_mcap_for_timestamp",
    "find_mcaps_for_interval",
    "generate_download_script",
    "log_debug",
    "log_error",
    "log_info",
    "log_warning",
    "plan_job_snipping_operations",
    "process_all_jobs",
    "process_job_markers",
    "query_raas_jobs",
    "set_log_level",
]


def __getattr__(name: str):
    """Expose the current logging state without copying mutable module data."""
    if name == "CURRENT_LOG_LEVEL":
        from . import logging_utils

        return logging_utils.CURRENT_LOG_LEVEL
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
