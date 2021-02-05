# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import time
from datetime import timedelta
from typing import List

import pytest
from osparc import ApiClient, JobsApi, SolversApi
from osparc.models import Job, JobOutput, JobStatus, Solver
from osparc.rest import ApiException


@pytest.fixture()
def jobs_api(api_client: ApiClient):
    return JobsApi(api_client)


def test_create_job(solvers_api: SolversApi, jobs_api: JobsApi):
    solver = solvers_api.get_solver_by_name_and_version(
        solver_name="simcore/services/comp/slepper", version="latest"
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


def test_run_job(solvers_api: SolversApi, jobs_api: JobsApi):

    solver = solvers_api.get_solver_by_name_and_version(
        solver_name="simcore/services/comp/slepper", version="latest"
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
