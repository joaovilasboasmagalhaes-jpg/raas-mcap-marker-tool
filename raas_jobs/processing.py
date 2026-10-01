"""RaaS marker processing and MCAP merge/snip planning."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .downloads import build_mcap_download_command
from .mcap import extract_mcap_file_list, find_mcaps_for_interval
from .timestamps import UTC_PLUS_2, convert_timestamp_to_utc


def coalesce_intervals(
    intervals: List[Tuple[datetime, datetime]],
) -> List[Tuple[datetime, datetime]]:
    """Merge sorted-by-time intervals that overlap or touch."""
    if not intervals:
        return []

    sorted_intervals = sorted(intervals)
    coalesced: List[Tuple[datetime, datetime]] = [sorted_intervals[0]]
    for interval_start, interval_end in sorted_intervals[1:]:
        current_start, current_end = coalesced[-1]
        if interval_start <= current_end:
            coalesced[-1] = (current_start, max(current_end, interval_end))
        else:
            coalesced.append((interval_start, interval_end))
    return coalesced


def plan_job_snipping_operations(
    job_id: str,
    markers: List[Dict[str, Any]],
    dest_dir: str,
    threshold_seconds: float = 10.0,
) -> Dict[str, Any]:
    """Calculate deduplicated merge and snip operations for a job."""
    del dest_dir, threshold_seconds
    merge_operations: Dict[Tuple[str, ...], str] = {}
    snip_operations: List[Dict[str, Any]] = []
    interval_operations: List[Dict[str, Any]] = []

    for marker in markers:
        window_start = marker.get("windowStart")
        window_end = marker.get("windowEnd")
        mcap_paths = marker.get("mcapFiles") or []
        if not window_start or not window_end or not mcap_paths:
            continue

        interval_operations.append(
            {
                "start": datetime.fromisoformat(window_start),
                "end": datetime.fromisoformat(window_end),
                "mcapFiles": set(mcap_paths),
            }
        )

    interval_operations.sort(key=lambda operation: operation["start"])
    coalesced_operations: List[Dict[str, Any]] = []
    for operation in interval_operations:
        if (
            coalesced_operations
            and operation["start"] <= coalesced_operations[-1]["end"]
        ):
            current = coalesced_operations[-1]
            current["end"] = max(current["end"], operation["end"])
            current["mcapFiles"].update(operation["mcapFiles"])
        else:
            coalesced_operations.append(
                {
                    "start": operation["start"],
                    "end": operation["end"],
                    "mcapFiles": set(operation["mcapFiles"]),
                }
            )

    for operation in coalesced_operations:
        mcap_basenames = sorted(
            os.path.basename(path.strip()) for path in operation["mcapFiles"]
        )
        if len(mcap_basenames) == 1:
            input_file = mcap_basenames[0]
        else:
            files_tuple = tuple(mcap_basenames)
            if files_tuple not in merge_operations:
                merge_output = (
                    f"merged_{len(merge_operations)}_{mcap_basenames[0][:19]}"
                    f"_to_{mcap_basenames[-1][20:39]}.mcap"
                )
                merge_operations[files_tuple] = merge_output
            input_file = merge_operations[files_tuple]

        window_start = operation["start"].isoformat()
        window_end = operation["end"].isoformat()
        start_tag = window_start.replace(":", "-").replace("+", "_plus_")
        end_tag = window_end.replace(":", "-").replace("+", "_plus_")
        snip_output = f"snipped_marker_{len(snip_operations)}_{start_tag}_to_{end_tag}.mcap"
        snip_operations.append(
            {
                "inputFilename": input_file,
                "outputFilename": snip_output,
                "windowStart": window_start,
                "windowEnd": window_end,
                "durationSeconds": (operation["end"] - operation["start"]).total_seconds(),
                "sourceMcaps": mcap_basenames,
            }
        )

    commands: List[str] = []
    for files_tuple, merge_output in merge_operations.items():
        inputs = " ".join(f'"{filename}"' for filename in files_tuple)
        commands.append(f'mcap merge --allow-duplicate-metadata {inputs} -o "{merge_output}"')
    for snip in snip_operations:
        commands.append(
            f'mcap filter "{snip["inputFilename"]}" --start "{snip["windowStart"]}" '
            f'--end "{snip["windowEnd"]}" -o "{snip["outputFilename"]}"'
        )

    return {
        "jobId": job_id,
        "mergeOperations": [
            {"inputFiles": list(files), "outputFile": output}
            for files, output in merge_operations.items()
        ],
        "snipOperations": snip_operations,
        "commands": commands,
    }


def process_job_markers(
    job: Dict[str, Any],
    evaluator: Union[str, List[str]],
    threshold_seconds: float = 10.0,
    tz: Optional[timezone] = UTC_PLUS_2,
    dest_base_path: str = "~/mcap",
    expand_user: bool = True,
    download_all_mcaps: bool = False,
) -> Dict[str, Any]:
    """Process matching markers and prepare their MCAP download and snip plan."""
    target_evaluators = {evaluator} if isinstance(evaluator, str) else set(evaluator)
    raw_markers = job.get("markers") or []
    all_job_mcap_files = extract_mcap_file_list(job.get("outputMcapFiles"))
    job_id = job.get("id") or "unknown_job"

    matching_markers = []
    marker_windows: List[Tuple[int, datetime, datetime]] = []
    converted_log_times = []
    window_delta = timedelta(seconds=threshold_seconds)

    for marker in raw_markers:
        if marker.get("evaluator") not in target_evaluators:
            continue

        raw_log_time = marker.get("loggerTime")
        converted_dt = None
        window_start = None
        window_end = None
        matching_mcaps: List[str] = []
        if raw_log_time is not None:
            converted_dt = convert_timestamp_to_utc(raw_log_time, tz=tz)
            converted_log_times.append(converted_dt)
            window_start = converted_dt - window_delta
            window_end = converted_dt + window_delta

        matching_markers.append(
            {
                "evaluator": marker.get("evaluator"),
                "rawLoggerTime": raw_log_time,
                "convertedLoggerTime": converted_dt.isoformat() if converted_dt else None,
                "windowStart": window_start.isoformat() if window_start else None,
                "windowEnd": window_end.isoformat() if window_end else None,
                "mcapFiles": matching_mcaps,
            }
        )
        if window_start is not None and window_end is not None:
            marker_windows.append(
                (len(matching_markers) - 1, window_start, window_end)
            )

    coalesced_windows = coalesce_intervals(
        [(window_start, window_end) for _, window_start, window_end in marker_windows]
    )
    matched_mcaps_set: Set[str] = set()
    coalesced_markers: List[Dict[str, Any]] = []
    mcaps_by_interval: List[Tuple[datetime, datetime, List[str]]] = []
    for window_start, window_end in coalesced_windows:
        matching_mcaps = find_mcaps_for_interval(
            start_dt=window_start,
            end_dt=window_end,
            mcap_files=all_job_mcap_files,
            tz=tz,
        )
        matched_mcaps_set.update(matching_mcaps)
        mcaps_by_interval.append((window_start, window_end, matching_mcaps))
        coalesced_markers.append(
            {
                "windowStart": window_start.isoformat(),
                "windowEnd": window_end.isoformat(),
                "mcapFiles": matching_mcaps,
            }
        )

    for marker_index, marker_start, marker_end in marker_windows:
        for interval_start, interval_end, matching_mcaps in mcaps_by_interval:
            if interval_start <= marker_start and marker_end <= interval_end:
                matching_markers[marker_index]["mcapFiles"] = matching_mcaps
                break

    matched_mcaps_list = sorted(matched_mcaps_set)
    mcap_files_to_download = all_job_mcap_files if download_all_mcaps else matched_mcaps_list
    download_command = build_mcap_download_command(
        job=job,
        dest_base_path=dest_base_path,
        mcap_files=mcap_files_to_download,
        expand_user=expand_user,
    )

    destination_dir = f"{dest_base_path.rstrip('/')}/{job_id}_artifacts"
    if expand_user:
        destination_dir = os.path.expanduser(destination_dir)
    snipping_plan = plan_job_snipping_operations(
        job_id=job_id,
        markers=coalesced_markers,
        dest_dir=destination_dir,
        threshold_seconds=threshold_seconds,
    )

    return {
        "jobId": job_id,
        "outputBucket": job.get("outputBucket"),
        "outputMcapFiles": job.get("outputMcapFiles"),
        "matchedMcapFiles": matched_mcaps_list,
        "thresholdSeconds": threshold_seconds,
        "downloadCommand": download_command,
        "snippingPlan": snipping_plan,
        "evaluator": (
            list(target_evaluators)
            if len(target_evaluators) > 1
            else next(iter(target_evaluators))
        ),
        "markerCount": len(matching_markers),
        "markers": matching_markers,
        "convertedLogTimes": [datetime.isoformat(dt) for dt in converted_log_times],
    }


def process_all_jobs(
    jobs: List[Dict[str, Any]],
    evaluator: Union[str, List[str]],
    threshold_seconds: float = 10.0,
    tz: Optional[timezone] = UTC_PLUS_2,
    dest_base_path: str = "~/mcap",
    expand_user: bool = True,
    download_all_mcaps: bool = False,
) -> List[Dict[str, Any]]:
    """Process all supplied RaaS jobs."""
    return [
        process_job_markers(
            job=job,
            evaluator=evaluator,
            threshold_seconds=threshold_seconds,
            tz=tz,
            dest_base_path=dest_base_path,
            expand_user=expand_user,
            download_all_mcaps=download_all_mcaps,
        )
        for job in jobs
    ]
