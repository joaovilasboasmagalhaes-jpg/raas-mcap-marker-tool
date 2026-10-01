"""Generated MCAP download script creation and execution."""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from .logging_utils import log_error, log_info, write_raw


def generate_download_script(
    processed_jobs: List[Dict[str, Any]],
    output_filename: str = "download_mcaps.sh",
    output_dir: Optional[str] = None,
    make_executable: bool = True,
    dest_base_path: str = "~/mcap",
    expand_user: bool = True,
) -> str:
    """Generate a bash script containing download, merge, and snip commands."""
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(output_dir, exist_ok=True)
    script_path = os.path.join(output_dir, output_filename)
    jobs_with_downloads = [job for job in processed_jobs if job.get("downloadCommand")]

    script_lines = [
        "#!/usr/bin/env bash",
        "# Auto-generated MCAP download, merge, and snipping script",
        "set -u",
        "",
        "SUCCESS_COUNT=0",
        "ERROR_COUNT=0",
        "FAILED_JOBS=()",
        "",
        "print_colored() {",
        '    local color="$1" fd="$2" message="$3"',
        '    if [[ -t "$fd" && -z "${NO_COLOR:-}" ]]; then',
        '        printf "\\033[%sm%s\\033[0m\\n" "$color" "$message" >&"$fd"',
        '    elif [[ "$fd" == "2" ]]; then',
        '        printf "%s\\n" "$message" >&2',
        "    else",
        '        printf "%s\\n" "$message"',
        "    fi",
        "}",
        "",
        f'echo "Starting processing for {len(jobs_with_downloads)} jobs..."',
        'echo "--------------------------------------------------------"',
        "",
    ]

    for job in jobs_with_downloads:
        job_id = job.get("jobId", "unknown")
        command = job.get("downloadCommand")
        snipping_plan = job.get("snippingPlan") or {}
        snip_commands = snipping_plan.get("commands") or []
        merge_operation_count = len(snipping_plan.get("mergeOperations") or [])
        snip_operations = snipping_plan.get("snipOperations") or []
        destination_dir = f"{dest_base_path.rstrip('/')}/{job_id}_artifacts"
        if expand_user:
            destination_dir = os.path.expanduser(destination_dir)

        script_lines.append(
            f'print_colored 34 1 "=== [1/2] Downloading artifacts for job: {job_id} ==="'
        )
        script_lines.append(f"if {command}; then")
        script_lines.append(f'    print_colored 32 1 "[SUCCESS] Download finished for job {job_id}"')
        if snip_commands:
            script_lines.append(f'    WORK_DIR="{destination_dir}"')
            script_lines.append(f'    if [ -d "{destination_dir}/MCAP" ]; then')
            script_lines.append(f'        WORK_DIR="{destination_dir}/MCAP"')
            script_lines.append("    fi")
            script_lines.append(
                f'    print_colored 34 1 "=== [2/2] Running {len(snip_commands)} '
                'merge/snip operation(s) in $WORK_DIR ==="'
            )
            script_lines.append('    if [ -d "$WORK_DIR" ]; then')
            script_lines.append('        (cd "$WORK_DIR" && \\')
            for index, snip_command in enumerate(snip_commands):
                snip_index = index - merge_operation_count
                duration_log = ""
                if 0 <= snip_index < len(snip_operations):
                    snip_operation = snip_operations[snip_index]
                    duration_seconds = snip_operation.get("durationSeconds")
                    if duration_seconds is None:
                        duration_seconds = (
                            datetime.fromisoformat(snip_operation["windowEnd"])
                            - datetime.fromisoformat(snip_operation["windowStart"])
                        ).total_seconds()
                    duration_log = (
                        f' && print_colored 32 1 "[INFO] Snipped '
                        f'{snip_operation["outputFilename"]} duration: '
                        f'{duration_seconds:.3f} seconds"'
                    )
                connector = " && \\" if index < len(snip_commands) - 1 else ""
                script_lines.append(
                    f'         print_colored 34 1 "[STEP] {snip_command}" && '
                    f'{snip_command}{duration_log}{connector}'
                )
            script_lines.append("        )")
            script_lines.append("        if [ $? -eq 0 ]; then")
            script_lines.append(
                f'            print_colored 32 1 "[SUCCESS] Snipped MCAPs created successfully for job {job_id}"'
            )
            script_lines.append("            ((SUCCESS_COUNT++))")
            script_lines.append("        else")
            script_lines.append(
                f'            print_colored 31 2 "[ERROR] Merging/snipping failed for job {job_id} in $WORK_DIR"'
            )
            script_lines.append("            ((ERROR_COUNT++))")
            script_lines.append(f'            FAILED_JOBS+=("{job_id}")')
            script_lines.append("        fi")
            script_lines.append("    else")
            script_lines.append(
                f'        print_colored 31 2 "[ERROR] Destination directory {destination_dir} not found after download"'
            )
            script_lines.append("        ((ERROR_COUNT++))")
            script_lines.append(f'        FAILED_JOBS+=("{job_id}")')
            script_lines.append("    fi")
        else:
            script_lines.append("    ((SUCCESS_COUNT++))")

        script_lines.append("else")
        script_lines.append(f'    print_colored 31 2 "[ERROR] Failed download for job {job_id}"')
        script_lines.append("    ((ERROR_COUNT++))")
        script_lines.append(f'    FAILED_JOBS+=("{job_id}")')
        script_lines.append("fi")
        script_lines.append('echo "--------------------------------------------------------"')
        script_lines.append("")

    script_lines.extend(
        [
            'echo ""',
            'echo "=================== PIPELINE SUMMARY ==================="',
            f'echo "Total Jobs:     {len(jobs_with_downloads)}"',
            'echo "Successful:     ${SUCCESS_COUNT}"',
            'echo "Errors:         ${ERROR_COUNT}"',
            'if [ "${ERROR_COUNT}" -gt 0 ]; then',
            '    echo "Failed Job IDs:"',
            '    for failed_job in "${FAILED_JOBS[@]}"; do',
            '        echo "  - ${failed_job}"',
            "    done",
            '    echo ""',
            '    print_colored 33 2 "[TIP] If downloads failed, please check that the corresponding S3 bucket is properly mounted on your system (e.g. under /s3/...)."',
            "    exit 1",
            "else",
            '    echo "All downloads and snipping operations completed successfully!"',
            "    exit 0",
            "fi",
            "",
        ]
    )

    with open(script_path, "w", encoding="utf-8") as script_file:
        script_file.write("\n".join(script_lines))

    if make_executable:
        try:
            os.chmod(script_path, 0o755)
        except OSError:
            pass
    return script_path


def execute_download_script(script_path: str) -> int:
    """Execute a generated download script and return its exit code."""
    log_info(f"Executing download script: {script_path}")
    process = subprocess.Popen(
        ["bash", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        write_raw(line)
    returncode = process.wait()
    if returncode == 0:
        log_info("Downloads and snipping finished successfully.")
    else:
        log_error(f"Download script failed with exit code {returncode}.")
    return returncode
