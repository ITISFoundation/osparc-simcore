"""
    NOTE: All tests in this module run against the same simcore deployed stack. Which means that the results in one
    might affect the others. E.g. files uploaded in one test can be listed in rext

"""
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
import time
from operator import attrgetter
from pathlib import Path
from urllib.parse import quote_plus
from zipfile import ZipFile

import osparc
import pytest
from pytest import TempPathFactory
from pytest_simcore.helpers.utils_public_api import ServiceInfoDict, ServiceNameStr

osparc_VERSION = tuple(map(int, osparc.__version__.split(".")))
assert osparc_VERSION >= (0, 4, 3)


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def sleeper_solver(
    solvers_api: osparc.SolversApi,
    services_registry: dict[ServiceNameStr, ServiceInfoDict],
) -> osparc.Solver:
    # this part is tested in test_solvers_api so it becomes a fixture here

    sleeper = services_registry["sleeper_service"]
    solver: osparc.Solver = solvers_api.get_solver_release(
        solver_key=sleeper["name"], version=sleeper["version"]
    )

    assert isinstance(solver, osparc.Solver)
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
def uploaded_input_file(
    tmp_path_factory: TempPathFactory, files_api: osparc.FilesApi
) -> osparc.File:
    basedir: Path = tmp_path_factory.mktemp("uploaded_input_file")

    # produce an input file in place
    input_path = basedir / "file-with-number.txt"
    input_path.write_text("2")

    # upload resource to server
    # server returns a model of the resource: File
    input_file: osparc.File = files_api.upload_file(file=input_path)
    assert isinstance(input_file, osparc.File)
    assert input_file.filename == input_path.name

    return input_file


def test_list_jobs(
    solvers_api: osparc.SolversApi,
    sleeper_solver: osparc.Solver,
    uploaded_input_file: osparc.File,
):
    solver = sleeper_solver

    # should be first test, no jobs created!
    jobs = solvers_api.list_jobs(solver.id, solver.version)
    assert not jobs

    expected_jobs = []
    for n in range(3):
        job = solvers_api.create_job(
            solver.id,
            solver.version,
            job_inputs=osparc.JobInputs(
                {
                    "input_1": uploaded_input_file,
                    "input_2": 3 * n,  # sleep time in secs
                    "input_3": bool(n % 2),  # fail after sleep?
                    "input_4": n,  # walk distance in meters
                }
            ),
        )
        assert isinstance(job, osparc.Job)
        expected_jobs.append(job)

        jobs = solvers_api.list_jobs(solver.id, solver.version)
        assert sorted(jobs, key=attrgetter("name")) == sorted(
            expected_jobs, key=attrgetter("name")
        )


def test_create_job(
    uploaded_input_file: osparc.File,
    solvers_api: osparc.SolversApi,
    sleeper_solver: osparc.Solver,
):
    solver = sleeper_solver

    # we know the solver has three inputs
    #
    job = solvers_api.create_job(
        solver.id,
        solver.version,
        osparc.JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 1,  # sleep time in secs
                "input_3": False,  # fail after sleep?
                "input_4": 2,  # walk distance in meters
            }
        ),
    )
    assert isinstance(job, osparc.Job)

    assert job.id
    assert job == solvers_api.get_job(solver.id, solver.version, job.id)

    # with positional arguments (repects displayOrder ?)
    # inputs=[input_file, 33, False] TODO: later, if time
    job2 = solvers_api.create_job(
        solver.id,
        solver.version,
        osparc.JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 1,
                "input_3": False,
                "input_4": 2,
            }
        ),
    )
    assert isinstance(job2, osparc.Job)

    # in principle, it create separate instances even if has the same inputs
    assert job.id != job2.id


@pytest.mark.parametrize(
    "expected_outcome",
    (
        "SUCCESS",
        "FAILED",
    ),
)
def test_run_job(
    uploaded_input_file: osparc.File,
    files_api: osparc.FilesApi,
    solvers_api: osparc.SolversApi,
    sleeper_solver: osparc.Solver,
    expected_outcome: str,
    tmp_path: Path,
):
    # get solver
    solver = sleeper_solver

    # create job
    job = solvers_api.create_job(
        solver.id,
        solver.version,
        osparc.JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 1,  # sleep time in secs
                "input_3": expected_outcome == "FAILED",  # fail after sleep?
                "input_4": 2,  # walk distance in meters
            }
        ),
    )

    # start job
    status: osparc.JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
    assert isinstance(status, osparc.JobStatus)

    assert status.state == "PUBLISHED"
    assert status.progress == 0
    # FIXME:
    # assert (
    #    job.created_at < status.submitted_at < (job.created_at + timedelta(seconds=2))
    # )

    # poll stop time-stamp
    while not status.stopped_at:
        time.sleep(0.5)
        status: osparc.JobStatus = solvers_api.inspect_job(
            solver.id, solver.version, job.id
        )
        assert isinstance(status, osparc.JobStatus)

        assert 0 <= status.progress <= 100

        print("Solver progress", f"{status.progress}/100", flush=True)

    # done, either successfully or with failures!
    assert status.progress == 100
    assert status.state == expected_outcome
    # FIXME: assert status.submitted_at < status.started_at
    # FIXME: assert status.started_at < status.stopped_at
    assert status.submitted_at < status.stopped_at

    # check solver outputs
    outputs: osparc.JobOutputs = solvers_api.get_job_outputs(
        solver.id, solver.version, job.id
    )
    assert isinstance(outputs, osparc.JobOutputs)
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
        assert isinstance(output_file, osparc.File)
        assert isinstance(number, float)

        # output file exists
        assert files_api.get_file(output_file.id) == output_file

        # can download and open
        download_path: str = files_api.download_file(file_id=output_file.id)
        assert float(Path(download_path).read_text()), "contains a random number"

    else:
        # one of them is not finished
        assert output_file is None or number is None

    # download log (Added in on API version 0.4.0 / client version 0.5.0 )
    if osparc_VERSION >= (0, 5, 0):
        print("Testing output logfile ...")
        logfile: str = solvers_api.get_job_output_logfile(
            solver.id, solver.version, job.id
        )

        zip_path = Path(logfile)
        print(
            f"{zip_path=}",
            f"{zip_path.exists()=}",
            f"{zip_path.stat()=}",
            "\nUnzipping ...",
        )
        extract_dir = tmp_path / "log-extracted"
        extract_dir.mkdir()
        with ZipFile(f"{zip_path}") as fzip:
            fzip.extractall(extract_dir)

        logfiles = list(extract_dir.glob("*.log*"))
        print("Unzipped", logfiles[0], "contains:\n", logfiles[0].read_text())
        assert len(logfiles) == 1
        assert logfiles[0].read_text()


def test_sugar_syntax_on_solver_setup(
    solvers_api: osparc.SolversApi,
    sleeper_solver: osparc.Solver,
    uploaded_input_file: osparc.File,
):
    solver = sleeper_solver
    solver_tag = solver.id, solver.version

    job = solvers_api.create_job(
        job_inputs=osparc.JobInputs(
            {
                "input_1": uploaded_input_file,
                "input_2": 33,  # sleep time in secs
                "input_3": False,  # fail after sleep?
                "input_4": 2,  # walk distance in meters
            }
        ),
        *solver_tag,
    )
    assert isinstance(job, osparc.Job)

    assert job.runner_name == "solvers/{}/releases/{}".format(
        quote_plus(str(solver.id)), solver.version
    )
