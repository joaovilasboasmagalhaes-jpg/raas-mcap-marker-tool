"""MCAP download command construction."""

import os
from typing import Any, Dict, List, Optional

from .mcap import extract_mcap_file_list


def build_mcap_download_command(
    job: Dict[str, Any],
    dest_base_path: str = "~/mcap",
    mcap_files: Optional[List[str]] = None,
    expand_user: bool = True,
) -> Optional[str]:
    """Build the rsync command for the selected MCAP files in a job."""
    job_id = job.get("id") or "unknown_job"
    output_bucket = job.get("outputBucket") or ""
    if not output_bucket:
        return None

    raw_mcap_files = (
        extract_mcap_file_list(job.get("outputMcapFiles"))
        if mcap_files is None
        else mcap_files
    )

    filenames: List[str] = []
    seen = set()
    for mcap_file in raw_mcap_files:
        filename = os.path.basename(mcap_file.strip())
        if filename and filename not in seen:
            seen.add(filename)
            filenames.append(filename)

    if not filenames:
        return None

    if output_bucket.startswith("s3://"):
        source_path = "/s3/" + output_bucket[5:]
    elif output_bucket.startswith("/s3/"):
        source_path = output_bucket
    else:
        source_path = f"/s3/{output_bucket.lstrip('/')}"
    source_path = source_path.rstrip("/") + "/"

    destination_path = f"{dest_base_path.rstrip('/')}/{job_id}_artifacts"
    if expand_user:
        destination_path = os.path.expanduser(destination_path)

    include_parts = ['--include="MCAP"']
    include_parts.extend(f'--include="{filename}"' for filename in filenames)
    include_flags = " ".join(include_parts)

    return (
        "rsync --progress --partial --verbose --human-readable --prune-empty-dirs --recursive "
        f'{include_flags} --exclude="*" -a {source_path} {destination_path}'
    )
