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
from typing import Any, Dict
from urllib.parse import quote_plus

import pytest
from osparc import FilesApi, SolversApi
from osparc.models import File, Job, JobInputs, JobOutputs, JobStatus, Solver


@pytest.fixture
def sleeper_solver(
    solvers_api: SolversApi,
    services_registry: Dict[str, Any],
) -> Solver:
    # this part is tested in test_solvers_api so it becomes a fixture here

    sleeper = services_registry["sleeper_service"]
    solver: Solver = solvers_api.get_solver_release(
        solver_key=sleeper["name"], version=sleeper["version"]
    )

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

    assert isinstance(solver, Solver)
    return solver


@pytest.fixture()
def uploaded_input_file(tmpdir, files_api: FilesApi) -> File:

    # produce an input file in place
    input_path = Path(tmpdir) / "file-with-number.txt"
    input_path.write_text("33")

    # upload resource to server
    # server returns a model of the resource: File
    input_file: File = files_api.upload_file(file=input_path)
    assert isinstance(input_file, File)
    assert input_file.filename == input_path.name

    return input_file


def test_create_job(
    uploaded_input_file: File,
    solvers_api: SolversApi,
    sleeper_solver: Solver,
):
    solver = sleeper_solver

    # we know the solver has three inputs
    #
    job = solvers_api.create_job(
        solver.id,
        solver.version,
        JobInputs({"input_1": uploaded_input_file, "input_2": 33, "input_3": False}),
    )
    assert isinstance(job, Job)

    assert job.id
    assert job == solvers_api.get_job(solver.id, solver.version, job.id)

    # with positional arguments (repects displayOrder ?)
    # inputs=[input_file, 33, False] TODO: later, if time
    job2 = solvers_api.create_job(
        solver.id,
        solver.version,
        JobInputs({"input_1": uploaded_input_file, "input_2": 33, "input_3": False}),
    )
    assert isinstance(job2, Job)

    # in principle, it create separate instances even if has the same inputs
    assert job.id != job2.id


def test_run_job(
    uploaded_input_file: File,
    files_api: FilesApi,
    solvers_api: SolversApi,
    sleeper_solver: Solver,
):
    # get solver
    solver = sleeper_solver

    # create job
    job = solvers_api.create_job(
        solver.id,
        solver.version,
        JobInputs({"input_1": uploaded_input_file, "input_2": 35, "input_3": True}),
    )

    # start job
    status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
    assert isinstance(status, JobStatus)

    assert status.state == "undefined"
    assert status.progress == 0
    assert (
        job.created_at < status.submitted_at < (job.created_at + timedelta(seconds=2))
    )

    # poll stop time-stamp
    while not status.stopped_at:
        time.sleep(0.5)
        status: JobStatus = solvers_api.inspect_job(solver.id, solver.version, job.id)
        assert isinstance(status, JobStatus)

        print("Solver progress", f"{status.progress}/100", flush=True)

    # done, either successfully or with failures!
    assert status.progress == 100
    assert status.state in ["success", "failed"]
    assert status.submitted_at < status.started_at
    assert status.started_at < status.stopped_at

    # check solver outputs
    # FIXME: client auto-generator does not support polymorphism in responses(i.e response)
    # https://openapi-generator.tech/docs/generators/python-legacy#schema-support-feature
    outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)
    assert isinstance(outputs, JobOutputs)
    assert outputs.job_id == job.id
    assert len(outputs.results) == 2

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
    output_file = outputs.results["output_1"]
    number = outputs.results["output_2"]
    assert isinstance(output_file, File)
    assert isinstance(number, float)

    # file exists in the cloud
    # FIXME: when director-v2 is connected instead of fake
    # assert files_api.get_file(output_file.id) == output_file


def test_sugar_syntax_on_solver_setup(
    solvers_api: SolversApi,
    sleeper_solver: Solver,
):
    solver = sleeper_solver
    solver_tag = solver.id, solver.version

    job = solvers_api.create_job(
        job_inputs=JobInputs({"input_2": 33, "input_3": False}), *solver_tag
    )
    assert isinstance(job, Job)

    assert job.runner_name == "solvers/{}/releases/{}".format(
        quote_plus(str(solver.id)), solver.version
    )
