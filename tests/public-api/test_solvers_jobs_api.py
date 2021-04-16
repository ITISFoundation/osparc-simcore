"""
    NOTE: All tests in this module run against the same simcore deployed stack. Which means that the results in one
    might affect the others. E.g. files uploaded in one test can be listed in rext

"""

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import time

# from datetime import timedelta
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote_plus

import pytest
from osparc import FilesApi, SolversApi
from osparc.models import File, Job, JobInputs, JobOutputs, JobStatus, Solver


@pytest.fixture(scope="module")
def sleeper_solver(
    solvers_api: SolversApi,
    services_registry: Dict[str, Any],
) -> Solver:
    # this part is tested in test_solvers_api so it becomes a fixture here

    sleeper = services_registry["sleeper_service"]
    solver: Solver = solvers_api.get_solver_release(
        solver_key=sleeper["name"], version=sleeper["version"]
    )

    assert isinstance(solver, Solver)
    assert solver.version == "2.1.1"

    # returns Dict[SolverInputSchema] and SolverInputSchema is a schema?
    # solvers_api.get_solver_inputs(name = solver.name, )
    #
    #
    # 'input_1': {'description': 'Pick a file containing only one '
    #                             'integer',
    #             'displayOrder': 1,
    #             'fileToKeyMap': {'single_number.txt': 'input_1'},
    #             'label': 'File with int number',
    #             'type': 'data:text/plain'},
    # 'input_2': {'defaultValue': 2,
    #             'description': 'Choose an amount of time to sleep',
    #             'displayOrder': 2,
    #             'label': 'Sleep interval',
    #             'type': 'integer',
    #             'unit': 'second'},
    # 'input_3': {'defaultValue': False,
    #             'description': 'If set to true will cause service to '
    #                             'fail after it sleeps',
    #             'displayOrder': 3,
    #             'label': 'Fail after sleep',
    #             'type': 'boolean'},
    # 'input_4': {'defaultValue': 0,
    #             'description': 'It will first walk the distance to '
    #                             'bed',
    #             'displayOrder': 4,
    #             'label': 'Distance to bed',
    #             'type': 'integer',
    #             'unit': 'meter'}},
    return solver


@pytest.fixture(scope="module")
def uploaded_input_file(tmpdir_factory, files_api: FilesApi) -> File:

    tmpdir = tmpdir_factory.mktemp("uploaded_input_file")

    # produce an input file in place
    input_path = Path(tmpdir) / "file-with-number.txt"
    input_path.write_text("2")

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
        JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 1,  # sleep time in secs
                "input_3": False,  # fail after sleep?
                "input_4": 2,  # walk distance in meters
            }
        ),
    )
    assert isinstance(job, Job)

    assert job.id
    assert job == solvers_api.get_job(solver.id, solver.version, job.id)

    # with positional arguments (repects displayOrder ?)
    # inputs=[input_file, 33, False] TODO: later, if time
    job2 = solvers_api.create_job(
        solver.id,
        solver.version,
        JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 1,
                "input_3": False,
                "input_4": 2,
            }
        ),
    )
    assert isinstance(job2, Job)

    # in principle, it create separate instances even if has the same inputs
    assert job.id != job2.id


@pytest.mark.parametrize("expected_outcome", ("SUCCESS", "FAILED"))
def test_run_job(
    uploaded_input_file: File,
    files_api: FilesApi,
    solvers_api: SolversApi,
    sleeper_solver: Solver,
    expected_outcome: str,
):
    # get solver
    solver = sleeper_solver

    # create job
    job = solvers_api.create_job(
        solver.id,
        solver.version,
        JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 1,  # sleep time in secs
                "input_3": expected_outcome == "FAILED",  # fail after sleep?
                "input_4": 2,  # walk distance in meters
            }
        ),
    )

    # start job
    status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
    assert isinstance(status, JobStatus)

    assert status.state == "PUBLISHED"
    assert status.progress == 0
    # FIXME:
    # assert (
    #    job.created_at < status.submitted_at < (job.created_at + timedelta(seconds=2))
    # )

    # poll stop time-stamp
    while not status.stopped_at:
        time.sleep(0.5)
        status: JobStatus = solvers_api.inspect_job(solver.id, solver.version, job.id)
        assert isinstance(status, JobStatus)

        assert 0 <= status.progress <= 100

        print("Solver progress", f"{status.progress}/100", flush=True)

    # done, either successfully or with failures!
    assert status.progress == 100
    assert status.state == expected_outcome
    # FIXME: assert status.submitted_at < status.started_at
    # FIXME: assert status.started_at < status.stopped_at
    assert status.submitted_at < status.stopped_at

    # check solver outputs
    outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)
    assert isinstance(outputs, JobOutputs)
    assert outputs.job_id == job.id
    assert len(outputs.results) == 2

    # 'outputs': {'output_1': {'description': 'Integer is generated in range [1-9]',
    #                         'displayOrder': 1,
    #                         'fileToKeyMap': {'single_number.txt': 'output_1'},
    #                         'label': 'File containing one random integer',
    #                         'type': 'data:text/plain'},
    #             'output_2': {'description': 'Interval is generated in range '
    #                                         '[1-9]',
    #                         'displayOrder': 2,
    #                         'label': 'Random sleep interval',
    #                         'type': 'integer',
    #                         'unit': 'second'}},

    output_file = outputs.results["output_1"]
    number = outputs.results["output_2"]

    assert status.state == expected_outcome

    if expected_outcome == "SUCCESS":
        assert isinstance(output_file, File)
        assert isinstance(number, float)

        # output file exists
        assert files_api.get_file(output_file.id) == output_file

        # can download and open
        download_path: str = files_api.download_file(file_id=output_file.id)
        assert float(Path(download_path).read_text()), "contains a random number"

    else:
        # one of them is not finished
        assert output_file is None or number is None


def test_sugar_syntax_on_solver_setup(
    solvers_api: SolversApi,
    sleeper_solver: Solver,
    uploaded_input_file: File,
):
    solver = sleeper_solver
    solver_tag = solver.id, solver.version

    job = solvers_api.create_job(
        job_inputs=JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 33,  # sleep time in secs
                "input_3": False,  # fail after sleep?
                "input_4": 2,  # walk distance in meters
            }
        ),
        *solver_tag,
    )
    assert isinstance(job, Job)

    assert job.runner_name == "solvers/{}/releases/{}".format(
        quote_plus(str(solver.id)), solver.version
    )
