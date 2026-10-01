# RaaS MCAP Marker Tool

## Quick Usage

Install the Python dependency from this directory:

```bash
python3 -m pip install -r requirements.txt
```

Run the tool from the repository root:

```bash
python3 query_jobs.py \
  --software-version ad_make_release_2610_ef_066_048_000_manual_73275_20260921T084707 \
  --evaluator ltmb_map_invalidation_obstacles_in_corridor
```

The command queries successful `pbs` RaaS jobs, finds markers for the evaluator, and creates `download_mcaps.sh`.

Execute the generated download, merge, and snipping pipeline with:

```bash
python3 query_jobs.py \
  --software-version ad_make_release_2610_ef_066_048_000_manual_73275_20260921T084707 \
  --evaluator ltmb_map_invalidation_obstacles_in_corridor \
  --execute
```

The generated script downloads artifacts below `~/mcap`, then runs the planned `mcap merge` and `mcap filter` commands. It logs the duration of every filtered interval.

Preview the available options without querying the API:

```bash
python3 query_jobs.py --help
```

## Prerequisites

- Python 3 with the `requests` package installed.
- Access to the Marker Insight GraphQL v2 endpoint.
- The relevant S3 bucket mounted under `/s3/...` for `rsync` downloads.
- `rsync` installed.
- The MCAP CLI installed and available as `mcap`.

The tool does not download files directly through an S3 SDK. The generated script uses `rsync` against the mounted `/s3/...` path.

## Common Options

| Option | Short form | Default | Purpose |
| --- | --- | --- | --- |
| `--software-version` | `-s` | The value in the CLI help | RaaS software or AdMake version to query. |
| `--evaluator` | `-e` | The value in the CLI help | Marker evaluator to keep. |
| `--playback-mode` | `-p` | `pbs` | Playback mode filter. |
| `--job-state` | `-j` | `SUCCESSFUL` | Job state filter. |
| `--dest-base-path` | `-d` | `~/mcap` | Root directory for downloaded job artifacts. |
| `--threshold` | `-t` | `10.0` | Seconds added before and after each marker. |
| `--script-name` | `-o` | `download_mcaps.sh` | Name of the generated shell script. |
| `--download-all-mcaps` | | Disabled | Download every MCAP from each matching job instead of only the MCAPs covering marker intervals. |
| `--execute` | `-x` | Disabled | Execute the generated shell script after creating it. |
| `--log-level` | `-l` | `INFO` | Use `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |

For example, use a five-second context window and a separate script name:

```bash
python3 query_jobs.py \
  -s software_version \
  -e evaluator_name \
  --threshold 5 \
  --script-name download_obstacle_markers.sh
```

## How It Works

1. The GraphQL API is queried for jobs matching the software version, evaluator, playback mode, and job state.
2. Markers are filtered to the requested evaluator.
3. Each marker timestamp is converted to the configured timezone, which defaults to UTC+2.
4. A context interval is created around each marker:

   ```text
   [marker time - threshold, marker time + threshold]
   ```

5. Overlapping or exactly touching marker intervals are coalesced into one unified interval. Separate intervals remain separate.
6. MCAP filenames are parsed for their start and end timestamps. Every MCAP overlapping a unified interval is associated with that interval.
7. Only the required MCAP files are included in the generated `rsync` command, unless `--download-all-mcaps` is used.
8. If an interval spans multiple MCAP files, those files are merged once with `mcap merge`.
9. The merged file, or the single source MCAP, is filtered with `mcap filter` to the unified interval.
10. The generated script reports download status, merge/filter steps, failures, and the requested duration of each snipped MCAP.

MCAP interval matching uses inclusive boundaries. An MCAP that meets the requested interval exactly at its start or end is included.

## Generated Files

The tool creates `raas_jobs/download_mcaps.sh` when it runs. This file is generated
for the selected jobs and should not be committed.

For each job with matching MCAP files, the generated script uses a directory like:

```text
~/mcap/<job-id>_artifacts/
```

Depending on the mounted S3 layout, the files may be inside an additional `MCAP/` directory. The script detects that directory before running MCAP operations.

Intermediate and output files use names similar to:

```text
merged_0_<first-mcap>_to_<last-mcap>.mcap
snipped_marker_0_<start>_to_<end>.mcap
```

The script continues processing other jobs after a failure and exits with status `1` if any job fails.

## Python API

The original `query_jobs.py` module remains a compatibility facade. The implementation is split into the `raas_jobs` package:

```python
from raas_jobs import process_job_markers, query_raas_jobs

jobs = query_raas_jobs(
    software_version="software_version",
    evaluator="evaluator_name",
)
processed_job = process_job_markers(
    job=jobs[0],
    evaluator="evaluator_name",
    threshold_seconds=10.0,
)
```

The main modules are:

- `graphql_api.py`: GraphQL query and response handling.
- `timestamps.py`: timestamp parsing and timezone conversion.
- `mcap.py`: MCAP filename parsing and interval matching.
- `processing.py`: marker filtering, interval coalescing, MCAP association, and operation planning.
- `downloads.py`: `rsync` command construction.
- `scripts.py`: generated shell script creation and execution.
- `logging_utils.py`: simple colored logging helpers.

## Tests

Run the focused test suite from the tool directory:

```bash
python3 -m unittest discover -s test -v
```

The tests cover timestamp conversion, MCAP matching, GraphQL payload construction, interval coalescing, download commands, and generated script content.
