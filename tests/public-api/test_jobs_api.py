"""
    NOTE: All tests in this module run against the same simcore deployed stack. Which means that the results in one
    might affect the others. E.g. files uploaded in one test can be listed in rext

"""

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List

import pytest
from osparc import ApiClient, FilesApi, JobsApi, SolversApi
from osparc.models import File, Job, JobOutput, JobStatus, Solver
from osparc.rest import ApiException


@pytest.fixture()
def jobs_api(api_client: ApiClient):
    return JobsApi(api_client)


def test_create_job(
    files_api: FilesApi,
    solvers_api: SolversApi,
    jobs_api: JobsApi,
    services_registry: Dict[str, Any],
    tmpdir,
):

    sleeper = services_registry["sleeper_service"]

    # Get resource solver by name
    #  - name is a unique identifier given by the server
    #  - no need for UUIDs!
    solver: Solver = solvers_api.get_solver(name="{name}:{version}".format(**sleeper))
    assert isinstance(solver, Solver)

    # returns Dict[SolverInputSchema] and SolverInputSchema is a schema?
    # solvers_api.get_solver_inputs(name = solver.name, )
    # "inputs":
    #  {
    #    "input_1": {
    #         "displayOrder": 1,
    #         "label": "File with int number",
    #         "description": "Pick a file containing only one integer",
    #         "type": "data:text/plain",
    #         },
    #     "input_2": {
    #         "displayOrder": 2,
    #         "label": "Sleep interval",
    #         "description": "Choose an amount of time to sleep",
    #         "type": "integer",
    #         "defaultValue": 2,
    #         "unit": null,
    #         },
    #     "input_3": {
    #         "displayOrder": 3,
    #         "label": "Fail after sleep",
    #         "description": "If set to true will cause service to fail after it sleeps",
    #         "type": "boolean",
    #         "defaultValue": false,
    #         "unit": null,
    #         }
    #     },

    # produce an input file in place
    input_path = Path(tmpdir) / "file-with-number.txt"
    input_path.write_text("33")

    # upload resource to server
    # server returns a model of the resource: File
    input_file: File = files_api.upload_file(file=input_path)
    assert isinstance(input_file, File)
    assert input_file.filename == input_path.name

    # we know the solver has three inputs
    #
    job = solvers_api.create_job(
        solver.name, inputs={"input_1": input_file, "input_2": 33, "input_3": False}
    )
    assert isinstance(job, Job)

    assert job.id
    assert job == jobs_api.get_job(job.id)

    # with positional arguments (repects displayOrder ?)
    job2 = solvers_api.create_job(solver.name, inputs=[input_file, 33, False])
    assert isinstance(job2, Job)

    # in principle, it create separate instances even if has the same inputs
    assert job.id != job2.id


def test_create_job_old(
    solvers_api: SolversApi, jobs_api: JobsApi, services_registry: Dict[str, Any]
):
    sleeper = services_registry["sleeper_service"]

    solver = solvers_api.get_solver_by_name_and_version(
        solver_name=sleeper["name"], version=sleeper["version"]
    )
    assert isinstance(solver, Solver)

    # requests resources for a job with given inputs
    job = solvers_api.create_job(solver.id, job_input=[])
    assert isinstance(job, Job)

    assert job.id
    assert job == jobs_api.get_job(job.id)

    # gets jobs granted for user with a given solver
    solver_jobs = solvers_api.list_jobs(solver.id)
    assert job in solver_jobs

    # I only have jobs from this solver ?
    all_jobs = jobs_api.list_all_jobs()
    assert len(solver_jobs) <= len(all_jobs)
    assert all(job in all_jobs for job in solver_jobs)


def test_run_job(
    files_api: FilesApi,
    solvers_api: SolversApi,
    jobs_api: JobsApi,
    services_registry: Dict[str, Any],
    tmpdir,
):
    # get solver
    sleeper = services_registry["sleeper_service"]
    solver: Solver = solvers_api.get_solver(name="{name}:{version}".format(**sleeper))

    # create job
    input_path = Path(tmpdir) / "file-with-number.txt"
    input_path.write_text("33")
    input_file: File = files_api.upload_file(file=input_path)

    job = solvers_api.create_job(
        solver.name, inputs={"input_1": input_file, "input_2": 33, "input_3": False}
    )

    # start job
    status: JobStatus = jobs_api.start_job(job.id)
    assert isinstance(status, JobStatus)

    assert status.state == "undefined"
    assert status.progress == 0
    assert (
        job.created_at < status.submitted_at < (job.created_at + timedelta(seconds=2))
    )

    # poll stop time-stamp
    while not status.stopped_at:
        time.sleep(0.5)
        status: JobStatus = jobs_api.inspect_job(job.id)
        assert isinstance(status, JobStatus)

        print("Solver progress", f"{status.progress}/100", flush=True)

    # done, either successfully or with failures!
    assert status.progress == 100
    assert status.state in ["success", "failed"]
    assert status.submitted_at < status.started_at
    assert status.started_at < status.stopped_at

    # check solver outputs
    # "output_1": {
    #   "displayOrder": 1,
    #   "label": "File containing one random integer",
    #   "description": "Integer is generated in range [1-9]",
    #   "type": "data:text/plain",
    # },
    # "output_2": {
    #   "displayOrder": 2,
    #   "label": "Random sleep interval",
    #   "description": "Interval is generated in range [1-9]",
    #   "type": "integer",
    #   "defaultValue": null,
    #   "unit": null,
    # }

    #  return list following display-order
    outputs: List[Any] = jobs_api.list_job_outputs(job.id)
    assert len(outputs) == 2

    output_file, int_value = outputs
    assert isinstance(output_file, File)
    assert isinstance(int_value, int)

    # file exists in the cloud
    assert files_api.get_file(output_file.id) == output_file

    # get output by name
    assert output_file == jobs_api.get_job_output(job.id, name="output_1")
    assert int_value == jobs_api.get_job_output(job.id, name="output_2")

    # returns named outputs
    named_outputs: Dict[str, Any] = jobs_api.list_job_outputs(job.id, named=True)
    assert len(named_outputs) == 2


def test_run_job_old(
    solvers_api: SolversApi, jobs_api: JobsApi, services_registry: Dict[str, Any]
):

    sleeper = services_registry["sleeper_service"]

    solver = solvers_api.get_solver_by_name_and_version(
        solver_name=sleeper["name"], version=sleeper["version"]
    )
    assert isinstance(solver, Solver)

    # requests resources for a job with given inputs
    job = solvers_api.create_job(solver.id, job_input=[])
    assert isinstance(job, Job)

    assert job.id
    assert job == jobs_api.get_job(job.id)

    # let's do it!
    status: JobStatus = jobs_api.start_job(job.id)
    assert isinstance(status, JobStatus)

    assert status.state == "undefined"
    assert status.progress == 0
    assert (
        job.created_at < status.submitted_at < (job.created_at + timedelta(seconds=2))
    )

    # poll stop time-stamp
    while not status.stopped_at:
        time.sleep(0.5)
        status: JobStatus = jobs_api.inspect_job(job.id)
        assert isinstance(status, JobStatus)

        print("Solver progress", f"{status.progress}/100", flush=True)

    # done, either successfully or with failures!
    assert status.progress == 100
    assert status.state in ["success", "failed"]
    assert status.submitted_at < status.started_at
    assert status.started_at < status.stopped_at

    # let's get the results
    try:
        outputs: List[JobOutput] = jobs_api.list_job_outputs(job.id)
        assert outputs

        for output in outputs:
            print(output)
            assert isinstance(output, JobOutput)

            assert output.job_id == job.id
            assert output == jobs_api.get_job_output(job.id, output.name)

    except ApiException as err:
        assert (
            status.state == "failed" and err.status == 404
        ), f"No outputs if solver run failed {err}"
