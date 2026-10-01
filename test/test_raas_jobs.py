import os
import stat
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from raas_jobs import (
    QUERY_RAAS_JOBS,
    build_mcap_download_command,
    coalesce_intervals,
    convert_timestamp_to_utc,
    extract_mcap_file_list,
    extract_mcap_time_range,
    find_mcaps_for_interval,
    generate_download_script,
    plan_job_snipping_operations,
    process_job_markers,
    query_raas_jobs,
)


class TestTimestamps(unittest.TestCase):
    def test_convert_timestamp__given_milliseconds__expect_utc_plus_two(self):
        result = convert_timestamp_to_utc(1789757800000)

        self.assertEqual(result.isoformat(), "2026-09-18T20:56:40+02:00")

    def test_convert_timestamp__given_naive_datetime__expect_utc_assumption(self):
        result = convert_timestamp_to_utc(datetime(2026, 9, 18, 18, 56, 40))

        self.assertEqual(result.isoformat(), "2026-09-18T20:56:40+02:00")


class TestMcapMatching(unittest.TestCase):
    def test_extract_mcap_data__given_nested_output__expect_flat_file_list(self):
        result = extract_mcap_file_list(
            {
                "first": ["first.mcap", None],
                "second": "second.mcap",
            }
        )

        self.assertEqual(result, ["first.mcap", "second.mcap"])

    def test_find_mcaps__given_overlapping_interval__expect_matching_files(self):
        mcap_files = [
            "2026-09-18_20-56-30_2026-09-18_20-56-45_first.mcap",
            "2026-09-18_20-57-00_2026-09-18_20-57-10_second.mcap",
        ]
        start, end = extract_mcap_time_range(
            "2026-09-18_20-56-40_2026-09-18_20-56-50_window.mcap"
        )

        result = find_mcaps_for_interval(start, end, mcap_files)

        self.assertEqual(result, [mcap_files[0]])


class TestGraphqlApi(unittest.TestCase):
    @patch("raas_jobs.graphql_api.requests.post")
    def test_query_raas_jobs__given_filters__expect_graphql_payload(self, post):
        response = Mock()
        response.json.return_value = {"data": {"raasJobs": [{"id": "job-42"}]}}
        post.return_value = response

        result = query_raas_jobs(
            software_version="software-42",
            evaluator="evaluator-42",
            playback_mode=None,
            job_state=None,
            endpoint_url="https://example.invalid/graphql",
            timeout=43,
            headers={"Authorization": "Bearer token"},
        )

        self.assertEqual(result, [{"id": "job-42"}])
        response.raise_for_status.assert_called_once_with()
        post.assert_called_once_with(
            url="https://example.invalid/graphql",
            json={
                "query": QUERY_RAAS_JOBS,
                "variables": {
                    "softwareVersion": ["software-42"],
                    "markersEvaluator": ["evaluator-42"],
                },
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer token",
            },
            timeout=43,
        )

    @patch("raas_jobs.graphql_api.requests.post")
    def test_query_raas_jobs__given_time_window__expect_triggered_datetime_variables(self, post):
        response = Mock()
        response.json.return_value = {"data": {"raasJobs": []}}
        post.return_value = response

        query_raas_jobs(
            evaluator="evaluator-42",
            playback_mode=None,
            job_state=None,
            start_triggered_datetime="2026-09-01T00:00:00Z",
            end_triggered_datetime="2026-09-24T23:59:59Z",
            endpoint_url="https://example.invalid/graphql",
        )

        post.assert_called_once_with(
            url="https://example.invalid/graphql",
            json={
                "query": QUERY_RAAS_JOBS,
                "variables": {
                    "markersEvaluator": ["evaluator-42"],
                    "startTriggeredDatetime": "2026-09-01T00:00:00Z",
                    "endTriggeredDatetime": "2026-09-24T23:59:59Z",
                },
            },
            headers={"Content-Type": "application/json"},
            timeout=60,
        )


class TestDownloadPlanning(unittest.TestCase):
    def test_coalesce_intervals__given_touching_windows__expect_one_interval(self):
        first_start = datetime.fromisoformat("2026-09-18T20:56:40+02:00")
        touching_boundary = datetime.fromisoformat("2026-09-18T20:56:50+02:00")
        final_end = datetime.fromisoformat("2026-09-18T20:57:00+02:00")

        result = coalesce_intervals(
            [(first_start, touching_boundary), (touching_boundary, final_end)]
        )

        self.assertEqual(result, [(first_start, final_end)])

    def test_build_download_command__given_selected_files__expect_rsync_filters(self):
        job = {
            "id": "job-42",
            "outputBucket": "s3://bucket/path",
        }

        result = build_mcap_download_command(
            job,
            dest_base_path="/tmp/mcap",
            mcap_files=["/source/first.mcap", "/other/first.mcap", "second.mcap"],
            expand_user=False,
        )

        self.assertEqual(
            result,
            'rsync --progress --partial --verbose --human-readable --prune-empty-dirs --recursive '
            '--include="MCAP" --include="first.mcap" --include="second.mcap" '
            '--exclude="*" -a /s3/bucket/path/ /tmp/mcap/job-42_artifacts',
        )

    def test_plan_snipping__given_repeated_multi_mcap_intervals__expect_separate_snips(self):
        markers = [
            {
                "windowStart": "2026-09-18T20:56:40+02:00",
                "windowEnd": "2026-09-18T20:56:50+02:00",
                "mcapFiles": [
                    "/tmp/second.mcap",
                    "/tmp/first.mcap",
                ],
            },
            {
                "windowStart": "2026-09-18T20:56:40+02:00",
                "windowEnd": "2026-09-18T20:56:50+02:00",
                "mcapFiles": [
                    "/tmp/first.mcap",
                    "/tmp/second.mcap",
                ],
            },
        ]

        result = plan_job_snipping_operations("job-42", markers, "/tmp/job-42")

        self.assertEqual(len(result["mergeOperations"]), 1)
        self.assertEqual(len(result["snipOperations"]), 2)
        self.assertNotEqual(
            result["snipOperations"][0]["outputFilename"],
            result["snipOperations"][1]["outputFilename"],
        )
        self.assertEqual(len(result["commands"]), 3)

    def test_process_job__given_markers_two_seconds_apart__expect_separate_operations(self):
        first_mcap = "2026-09-18_20-56-30_2026-09-18_20-56-45_first.mcap"
        second_mcap = "2026-09-18_20-56-45_2026-09-18_20-57-10_second.mcap"
        job = {
            "id": "job-42",
            "outputBucket": "s3://bucket/path",
            "outputMcapFiles": [first_mcap, second_mcap],
            "markers": [
                {
                    "evaluator": "target",
                    "loggerTime": "2026-09-18T20:56:40+02:00",
                },
                {
                    "evaluator": "target",
                    "loggerTime": "2026-09-18T20:56:42+02:00",
                },
            ],
        }

        result = process_job_markers(
            job,
            evaluator="target",
            dest_base_path="/tmp/mcap",
            expand_user=False,
        )

        self.assertEqual(result["matchedMcapFiles"], [first_mcap, second_mcap])
        self.assertEqual(result["markers"][0]["mcapFiles"], [first_mcap, second_mcap])
        self.assertEqual(result["markers"][1]["mcapFiles"], [first_mcap, second_mcap])
        self.assertEqual(len(result["snippingPlan"]["snipOperations"]), 2)
        self.assertEqual(
            result["snippingPlan"]["snipOperations"][0]["windowStart"],
            "2026-09-18T20:56:30+02:00",
        )
        self.assertEqual(
            result["snippingPlan"]["snipOperations"][0]["windowEnd"],
            "2026-09-18T20:56:50+02:00",
        )
        self.assertEqual(
            result["snippingPlan"]["snipOperations"][1]["windowStart"],
            "2026-09-18T20:56:32+02:00",
        )
        self.assertEqual(
            result["snippingPlan"]["snipOperations"][1]["windowEnd"],
            "2026-09-18T20:56:52+02:00",
        )
        self.assertEqual(
            [operation["durationSeconds"] for operation in result["snippingPlan"]["snipOperations"]],
            [20.0, 20.0],
        )

    def test_process_job__given_separated_windows__expect_separate_operations(self):
        first_mcap = "2026-09-18_20-56-30_2026-09-18_20-56-45_first.mcap"
        second_mcap = "2026-09-18_20-58-00_2026-09-18_20-58-15_second.mcap"
        job = {
            "id": "job-42",
            "outputBucket": "s3://bucket/path",
            "outputMcapFiles": [first_mcap, second_mcap],
            "markers": [
                {
                    "evaluator": "target",
                    "loggerTime": "2026-09-18T20:56:40+02:00",
                },
                {
                    "evaluator": "target",
                    "loggerTime": "2026-09-18T20:58:05+02:00",
                },
            ],
        }

        result = process_job_markers(
            job,
            evaluator="target",
            dest_base_path="/tmp/mcap",
            expand_user=False,
        )

        self.assertEqual(len(result["snippingPlan"]["snipOperations"]), 2)
        self.assertEqual(
            result["snippingPlan"]["snipOperations"][0]["windowStart"],
            "2026-09-18T20:56:30+02:00",
        )
        self.assertEqual(
            result["snippingPlan"]["snipOperations"][1]["windowStart"],
            "2026-09-18T20:57:55+02:00",
        )

    def test_generate_download_script__given_job__expect_executable_script(self):
        processed_jobs = [
            {
                "jobId": "job-42",
                "downloadCommand": "rsync --dry-run source destination",
                "snippingPlan": {
                    "commands": ["mcap filter input.mcap -o output.mcap"],
                    "mergeOperations": [],
                    "snipOperations": [
                        {
                            "outputFilename": "output.mcap",
                            "durationSeconds": 20.0,
                        }
                    ],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as output_dir:
            script_path = generate_download_script(
                processed_jobs,
                output_dir=output_dir,
                dest_base_path="/tmp/mcap",
                expand_user=False,
            )

            with open(script_path, encoding="utf-8") as script_file:
                script = script_file.read()

            mode = os.stat(script_path).st_mode
            self.assertTrue(mode & stat.S_IXUSR)
            self.assertIn("job-42", script)
            self.assertIn("mcap filter input.mcap -o output.mcap", script)
            self.assertIn("Snipped output.mcap duration: 20.000 seconds", script)


if __name__ == "__main__":
    unittest.main()
