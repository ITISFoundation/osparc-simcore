"""
    NOTE: All tests in this module run against the same simcore deployed stack. Which means that the results in one
    might affect the others. E.g. files uploaded in one test can be listed in rext

"""

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import time
from operator import attrgetter
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from zipfile import ZipFile

import osparc
import osparc.exceptions
import pytest
from osparc import FilesApi, SolversApi
from osparc.models import File, Job, JobInputs, JobOutputs, JobStatus, Solver
from tenacity import Retrying, TryAgain
from tenacity.after import after_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

OSPARC_CLIENT_VERSION = tuple(map(int, osparc.__version__.split(".")))
assert OSPARC_CLIENT_VERSION >= (0, 4, 3)


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def sleeper_solver(
    solvers_api: SolversApi,
    services_registry: dict[str, Any],
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


def test_list_jobs(
    solvers_api: SolversApi,
    sleeper_solver: Solver,
    uploaded_input_file: File,
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
            job_inputs=JobInputs(
                {
                    "input_1": uploaded_input_file,
                    "input_2": 3 * n,  # sleep time in secs
                    "input_3": bool(n % 2),  # fail after sleep?
                    "input_4": n,  # walk distance in meters
                }
            ),
        )
        assert isinstance(job, Job)
        expected_jobs.append(job)

        jobs = solvers_api.list_jobs(solver.id, solver.version)
        assert sorted(jobs, key=attrgetter("name")) == sorted(
            expected_jobs, key=attrgetter("name")
        )


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


_RETRY_POLICY_IF_LOGFILE_NOT_FOUND = dict(
    # only 404 are retried, the rest are failures
    retry=retry_if_exception_type(TryAgain),
    wait=wait_fixed(1),
    stop=stop_after_attempt(5),
    after=after_log(logger, logging.WARNING),
    reraise=True,
)


@pytest.mark.parametrize("expected_outcome", ("SUCCESS", "FAILED"))
def test_run_job(
    uploaded_input_file: File,
    files_api: FilesApi,
    solvers_api: SolversApi,
    sleeper_solver: Solver,
    expected_outcome: str,
    tmp_path: Path,
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

    # download log (Added in on API version 0.4.0 / client version 0.5.0 )
    if OSPARC_CLIENT_VERSION >= (0, 5, 0):
        print("Testing output logfile ...")

        # NOTE: https://github.com/itisfoundation/osparc-simcore/issues/3569 shows
        # that this test might not have the logs ready in time and returns a 404 (not found)
        # for that reason we do a few retries before giving up
        for attempt in Retrying(_RETRY_POLICY_IF_LOGFILE_NOT_FOUND):
            with attempt:
                try:
                    logfile: str = solvers_api.get_job_output_logfile(
                        solver.id, solver.version, job.id
                    )
                except osparc.exceptions.ApiException as err:
                    if err.status == 404:
                        raise TryAgain(
                            f"get_job_output_logfile failed with {err}"
                        ) from err

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
