"""MCAP filename parsing and interval matching."""

import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple, Union

from .timestamps import UTC_PLUS_2, convert_timestamp_to_utc


MCAP_TIMESTAMP_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})"
)
MCAP_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


def extract_mcap_time_range(
    mcap_path_or_name: str,
    tz: Optional[timezone] = UTC_PLUS_2,
) -> Optional[Tuple[datetime, datetime]]:
    """Extract the start and end datetime from an MCAP filename or URI."""
    match = MCAP_TIMESTAMP_PATTERN.search(mcap_path_or_name)
    if not match:
        return None

    target_tz = tz if tz is not None else timezone.utc
    start_string, end_string = match.group(1), match.group(2)
    try:
        start = datetime.strptime(start_string, MCAP_TIME_FORMAT).replace(tzinfo=target_tz)
        end = datetime.strptime(end_string, MCAP_TIME_FORMAT).replace(tzinfo=target_tz)
        return start, end
    except ValueError:
        return None


def extract_mcap_file_list(output_mcap_data: Any) -> List[str]:
    """Flatten the supported shapes of the outputMcapFiles field."""
    if not output_mcap_data:
        return []
    if isinstance(output_mcap_data, list):
        return [str(item) for item in output_mcap_data if item]
    if isinstance(output_mcap_data, dict):
        files: List[str] = []
        for value in output_mcap_data.values():
            if isinstance(value, list):
                files.extend(str(item) for item in value if item)
            elif isinstance(value, str):
                files.append(value)
        return files
    if isinstance(output_mcap_data, str):
        return [output_mcap_data]
    return []


def find_mcaps_for_interval(
    start_dt: datetime,
    end_dt: datetime,
    mcap_files: List[str],
    tz: Optional[timezone] = UTC_PLUS_2,
) -> List[str]:
    """Find MCAP files whose ranges overlap the inclusive target interval."""
    matching_mcaps: List[str] = []
    for mcap_file in mcap_files:
        time_range = extract_mcap_time_range(mcap_file, tz=tz)
        if time_range is not None:
            mcap_start, mcap_end = time_range
            if start_dt <= mcap_end and mcap_start <= end_dt:
                matching_mcaps.append(mcap_file)
    return matching_mcaps


def find_mcap_for_timestamp(
    timestamp: Union[int, float, str, datetime],
    mcap_files: List[str],
    tz: Optional[timezone] = UTC_PLUS_2,
) -> Optional[str]:
    """Find the first MCAP file whose range covers a timestamp."""
    target_dt = convert_timestamp_to_utc(timestamp, tz=tz)
    matching = find_mcaps_for_interval(target_dt, target_dt, mcap_files, tz=tz)
    return matching[0] if matching else None
