# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "matplotlib",
#     "osparc>=0.8.3.post0.dev26",
#     "tenacity",
#     "tqdm",
# ]
# ///


import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import osparc_client
from httpx import BasicAuth, Client, HTTPStatusError
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_exponential

_SOLVER_KEY = "simcore/services/comp/itis/sleeper"
_SOLVER_VERSION = "2.2.1"


def main(njobs: int, sleep_seconds: int, log_job: bool = False):
    assert njobs > 0, "Number of jobs must be greater than 0"
    assert sleep_seconds > 0, "Sleep seconds must be greater than 0"

    url = os.environ.get("OSPARC_API_URL")
    assert url
    key = os.environ.get("OSPARC_API_KEY")
    assert key
    secret = os.environ.get("OSPARC_API_SECRET")
    assert secret
    configuration = osparc_client.Configuration(host=url, username=key, password=secret)

    uploaded_files = []
    registered_functions = []
    job_statuses = dict()

    with osparc_client.ApiClient(configuration) as api_client:
        try:
            api_instance = osparc_client.FunctionsApi(api_client)
            job_api_instance = osparc_client.FunctionJobsApi(api_client)
            job_collection_api_instance = osparc_client.FunctionJobCollectionsApi(
                api_client
            )
            file_client_instance = osparc_client.FilesApi(api_client)
            user_api_instance = osparc_client.UsersApi(api_client)

            user_api_instance.get_my_profile()

            with TemporaryDirectory() as temp_dir, Path(temp_dir) as tmpdir:
                _file = tmpdir / "file_with_number.txt"
                _file.write_text(f"{sleep_seconds}")
                file_with_number = file_client_instance.upload_file(
                    file=f"{_file.resolve()}"
                )
                assert file_with_number.id
                uploaded_files.append(file_with_number)

            solver_function = osparc_client.Function(
                osparc_client.SolverFunction(
                    uid=None,
                    title="s4l-python-runner",
                    description="Run Python code using sim4life",
                    input_schema=osparc_client.JSONFunctionInputSchema(),
                    output_schema=osparc_client.JSONFunctionOutputSchema(),
                    solver_key=_SOLVER_KEY,
                    solver_version=_SOLVER_VERSION,
                    default_inputs={},
                )
            )
            print(f"Built function: {solver_function.to_dict()}\n")

            registered_function = api_instance.register_function(
                solver_function.model_dump()
            )
            registered_functions.append(registered_function)

            print(f"Registered function: {registered_function.to_dict()}\n")

            function_id = registered_function.to_dict().get("uid")
            assert function_id

            inputs = njobs * [
                {
                    "input_1": file_with_number,
                    "input_2": 5,
                    "input_3": "false",
                    "input_4": 0,
                    "input_5": 0,
                }
            ]

            function_jobs = api_instance.map_function(
                function_id=function_id,
                request_body=inputs,
            )

            print(f"function_job: {function_jobs.to_dict()}")
            function_job_ids = function_jobs.job_ids
            assert function_job_ids

            if log_job:
                job = job_api_instance.get_function_job(function_job_ids[0])
                print_job_logs(configuration, job.actual_instance.solver_job_id)

            for job_uid in function_job_ids:
                status = wait_until_done(job_api_instance, job_uid)
                job_statuses[status] = job_statuses.get(status, 0) + 1

            statuses = list(job_statuses.keys())
            counts = [job_statuses[status] for status in statuses]

            plt.figure(figsize=(6, 4))
            plt.bar(statuses, counts, color="skyblue")
            plt.xlabel("Job Status")
            plt.ylabel("Count")
            plt.title("Function Job Status Counts")
            plt.tight_layout()
            plt.show(block=True)

        finally:

            for file in uploaded_files:
                try:
                    file_client_instance.delete_file(file.id)
                    print(f"Deleted file {file.id}")
                except Exception as e:
                    print(f"Failed to delete file {file.id}: {e}")

            for function in registered_functions:
                function_uid = function.actual_instance.uid
                try:
                    api_instance.delete_function(function_uid)
                    print(f"Deleted function {function_uid}")
                except Exception as e:
                    print(f"Failed to delete function {function_uid}: {e}")


@retry(
    stop=stop_after_delay(timedelta(minutes=10)),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
)
def wait_until_done(function_api: osparc_client.FunctionJobsApi, function_job_uid: str):
    job_status = function_api.function_job_status(function_job_uid).status
    assert job_status in ("SUCCESS", "FAILED")
    return job_status


@retry(
    stop=stop_after_delay(timedelta(minutes=5)),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(HTTPStatusError),
    reraise=False,
)
def print_job_logs(configuration: osparc_client.Configuration, solver_job_uid: str):
    print(f"Logging job log for solver job UID: {solver_job_uid}")
    client = Client(
        base_url=configuration.host,
        auth=BasicAuth(
            username=configuration.username, password=configuration.password
        ),
    )
    with client.stream(
        "GET",
        f"/v0/solvers/{_SOLVER_KEY}/releases/{_SOLVER_VERSION}/jobs/{solver_job_uid}/logstream",
        timeout=10,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            for msg in json.loads(line).get("messages"):
                print(f"{datetime.now().isoformat()}: {msg}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-job", action="store_true", help="Log details of a single job"
    )
    parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=10,
        help="Number of seconds for the sleeper function (default: 10)",
    )
    parser.add_argument(
        "--njobs",
        type=int,
        default=100,
        help="Number of jobs to run (default: 100)",
    )
    args = parser.parse_args()
    main(njobs=args.njobs, sleep_seconds=args.sleep_seconds, log_job=args.log_job)
