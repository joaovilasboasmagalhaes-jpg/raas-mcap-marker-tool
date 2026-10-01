"""CLI and backward-compatible imports for the RaaS job utility."""

import argparse
import datetime
import json
import os

from raas_jobs import (
    GRAPHQL_ENDPOINT,
    MCAP_TIME_FORMAT,
    MCAP_TIMESTAMP_PATTERN,
    QUERY_RAAS_JOBS,
    UTC_PLUS_2,
    LogLevel,
    build_mcap_download_command,
    close_log_file,
    configure_log_file,
    convert_timestamp_to_utc,
    execute_download_script,
    extract_mcap_file_list,
    extract_mcap_time_range,
    find_mcap_for_timestamp,
    find_mcaps_for_interval,
    generate_download_script,
    log_debug,
    log_error,
    log_info,
    log_warning,
    plan_job_snipping_operations,
    process_all_jobs,
    process_job_markers,
    query_raas_jobs,
    set_log_level,
)
from raas_jobs import logging_utils


__all__ = [
    "CURRENT_LOG_LEVEL",
    "GRAPHQL_ENDPOINT",
    "MCAP_TIME_FORMAT",
    "MCAP_TIMESTAMP_PATTERN",
    "QUERY_RAAS_JOBS",
    "UTC_PLUS_2",
    "LogLevel",
    "build_mcap_download_command",
    "close_log_file",
    "configure_log_file",
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
    """Expose mutable logging state without copying it from the package."""
    if name == "CURRENT_LOG_LEVEL":
        return logging_utils.CURRENT_LOG_LEVEL
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Query Marker Insight GraphQL v2 for RaaS jobs matching a triggered-datetime window and evaluator."
    )
    parser.add_argument(
        "--start-time",
        "-S",
        default=None,
        help="ISO 8601 start of the triggered-datetime window, e.g. 2026-09-01T00:00:00Z "
        "(default: 24 hours before now)",
    )
    parser.add_argument(
        "--end-time",
        "-E",
        default=None,
        help="ISO 8601 end of the triggered-datetime window (default: now)",
    )
    parser.add_argument(
        "--software-version",
        "-s",
        default=None,
        help="Software version filter (default: none, all versions in the time window)",
    )
    parser.add_argument(
        "--evaluator",
        "-e",
        default="ltmb_map_invalidation_obstacles_in_corridor",
        help="Evaluator name (default: ltmb_map_invalidation_obstacles_in_corridor)",
    )
    parser.add_argument(
        "--playback-mode",
        "-p",
        default="pbs",
        help="Playback mode filter (default: pbs)",
    )
    parser.add_argument(
        "--job-state",
        "-j",
        default="SUCCESSFUL",
        help="Job state filter (default: SUCCESSFUL)",
    )
    parser.add_argument(
        "--dest-base-path",
        "-d",
        default="~/mcap",
        help="Base directory for MCAP downloads (default: ~/mcap)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=10.0,
        help="Margin in seconds before and after marker time for MCAP interval selection and snipping (default: 10.0)",
    )
    parser.add_argument(
        "--script-name",
        "-o",
        default="download_mcaps.sh",
        help="Filename for the generated download bash script (default: download_mcaps.sh)",
    )
    parser.add_argument(
        "--download-all-mcaps",
        action="store_true",
        help="Include all job MCAPs in the download command instead of only the matched MCAPs (default: False)",
    )
    parser.add_argument(
        "--execute",
        "-x",
        action="store_true",
        help="Automatically execute the generated download script to fetch the MCAP files",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level threshold (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Path to a file where all logged output is also recorded "
        "(default: logs/raas_jobs_<timestamp>.log)",
    )
    return parser


def main() -> int:
    """Query jobs, prepare MCAP operations, and optionally execute them."""
    args = build_argument_parser().parse_args()
    set_log_level(args.log_level)

    log_file_path = args.log_file or os.path.join(
        "logs", f"raas_jobs_{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}.log"
    )
    resolved_log_file_path = configure_log_file(log_file_path)
    log_info(f"Logging to file: {resolved_log_file_path}")

    now = datetime.datetime.now(datetime.timezone.utc)
    end_time = args.end_time or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    start_time = args.start_time or (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    log_info(
        f"Querying jobs for start_time='{start_time}', end_time='{end_time}', "
        f"evaluator='{args.evaluator}'..."
    )
    jobs = query_raas_jobs(
        evaluator=args.evaluator,
        software_version=args.software_version,
        playback_mode=args.playback_mode,
        job_state=args.job_state,
        start_triggered_datetime=start_time,
        end_triggered_datetime=end_time,
    )

    log_info(f"Retrieved {len(jobs)} jobs. Processing markers and download commands...")
    processed_jobs = process_all_jobs(
        jobs=jobs,
        evaluator=args.evaluator,
        threshold_seconds=args.threshold,
        dest_base_path=args.dest_base_path,
        download_all_mcaps=args.download_all_mcaps,
    )
    script_path = generate_download_script(
        processed_jobs=processed_jobs,
        output_filename=args.script_name,
        dest_base_path=args.dest_base_path,
    )
    log_info(f"Generated download bash script: {script_path}")

    log_debug("Processed jobs payload:")
    if logging_utils.CURRENT_LOG_LEVEL.value <= LogLevel.DEBUG.value:
        log_debug(json.dumps(processed_jobs, indent=2))

    if args.execute:
        return execute_download_script(script_path)
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    finally:
        close_log_file()
    raise SystemExit(exit_code)
