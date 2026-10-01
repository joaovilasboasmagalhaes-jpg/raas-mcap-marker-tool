"""Marker Insight GraphQL API access."""

from typing import Any, Dict, List, Optional, Union

import requests


GRAPHQL_ENDPOINT = "https://marker-insight.prod.aws.orionadp.com/api_v2/"

QUERY_RAAS_JOBS = """
query GetJobsWithMcap(
  $softwareVersion: [String!]
  $markersEvaluator: [String!]
  $playbackMode: String
  $jobState: String
) {
  raasJobs(
    softwareVersion: $softwareVersion
    markersEvaluator: $markersEvaluator
    playbackMode: $playbackMode
    jobState: $jobState
  ) {
    id
    outputMcapFiles
    outputBucket
    markers {
      evaluator
      loggerTime
    }
  }
}
"""


def query_raas_jobs(
    software_version: Union[str, List[str]],
    evaluator: Union[str, List[str]],
    playback_mode: Optional[str] = "pbs",
    job_state: Optional[str] = "SUCCESSFUL",
    endpoint_url: str = GRAPHQL_ENDPOINT,
    timeout: int = 60,
    headers: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Query the Marker Insight GraphQL v2 API for RaaS jobs."""
    software_versions = [software_version] if isinstance(software_version, str) else software_version
    evaluators = [evaluator] if isinstance(evaluator, str) else evaluator

    variables: Dict[str, Any] = {
        "softwareVersion": software_versions,
        "markersEvaluator": evaluators,
    }
    if playback_mode is not None:
        variables["playbackMode"] = playback_mode
    if job_state is not None:
        variables["jobState"] = job_state

    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    response = requests.post(
        url=endpoint_url,
        json={"query": QUERY_RAAS_JOBS, "variables": variables},
        headers=request_headers,
        timeout=timeout,
    )
    response.raise_for_status()

    result = response.json()
    if "errors" in result and result["errors"]:
        raise RuntimeError(f"GraphQL query returned errors: {result['errors']}")

    data = result.get("data") or {}
    return data.get("raasJobs", [])
