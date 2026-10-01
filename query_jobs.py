"""CLI and backward-compatible imports for the RaaS job utility."""

import argparse
import json

from raas_jobs import (
    GRAPHQL_ENDPOINT,
    MCAP_TIME_FORMAT,
    MCAP_TIMESTAMP_PATTERN,
    QUERY_RAAS_JOBS,
    UTC_PLUS_2,
    LogLevel,
    build_mcap_download_command,
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
        description="Query Marker Insight GraphQL v2 for RaaS jobs matching software version and evaluator."
    )
    parser.add_argument(
        "--software-version",
        "-s",
        default="ad_make_release_2610_ef_066_048_000_manual_73275_20260921T084707",
        help="Software version (default: ad_make_release_2610_ef_066_048_000_manual_73275_20260921T084707)",
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
    return parser


def main() -> int:
    """Query jobs, prepare MCAP operations, and optionally execute them."""
    args = build_argument_parser().parse_args()
    set_log_level(args.log_level)

    log_info(
        f"Querying jobs for software_version='{args.software_version}', "
        f"evaluator='{args.evaluator}'..."
    )
    jobs = query_raas_jobs(
        software_version=args.software_version,
        evaluator=args.evaluator,
        playback_mode=args.playback_mode,
        job_state=args.job_state,
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
        print(json.dumps(processed_jobs, indent=2))

    if args.execute:
        return execute_download_script(script_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
