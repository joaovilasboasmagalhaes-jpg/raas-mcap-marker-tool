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
  $startTriggeredDatetime: String
  $endTriggeredDatetime: String
) {
  raasJobs(
    softwareVersion: $softwareVersion
    markersEvaluator: $markersEvaluator
    playbackMode: $playbackMode
    jobState: $jobState
    startTriggeredDatetime: $startTriggeredDatetime
    endTriggeredDatetime: $endTriggeredDatetime
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
    evaluator: Union[str, List[str]],
    software_version: Optional[Union[str, List[str]]] = None,
    playback_mode: Optional[str] = "pbs",
    job_state: Optional[str] = "SUCCESSFUL",
    start_triggered_datetime: Optional[str] = None,
    end_triggered_datetime: Optional[str] = None,
    endpoint_url: str = GRAPHQL_ENDPOINT,
    timeout: int = 60,
    headers: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Query the Marker Insight GraphQL v2 API for RaaS jobs."""
    evaluators = [evaluator] if isinstance(evaluator, str) else evaluator

    variables: Dict[str, Any] = {
        "markersEvaluator": evaluators,
    }
    if software_version is not None:
        software_versions = [software_version] if isinstance(software_version, str) else software_version
        variables["softwareVersion"] = software_versions
    if playback_mode is not None:
        variables["playbackMode"] = playback_mode
    if job_state is not None:
        variables["jobState"] = job_state
    if start_triggered_datetime is not None:
        variables["startTriggeredDatetime"] = start_triggered_datetime
    if end_triggered_datetime is not None:
        variables["endTriggeredDatetime"] = end_triggered_datetime

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
