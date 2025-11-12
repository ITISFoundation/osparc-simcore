import logging
import os
import shutil
import tarfile
import time
from enum import Enum
from pathlib import Path

import osparc
from EmFdtdSimulator import EmFdtdMultiportSimulation
from s4l_v1._api.simwrappers import ApiSimulation
from XSimulator import Simulation, SolverSettings

assert osparc.__version__ == "0.4.3"

HOST = os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006")
KEY = os.environ.get("OSPARC_API_KEY")
SECRET = os.environ.get("OSPARC_API_SECRET")


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# We try to automatically deduce the isolve service that is suited best
class ISolveType(Enum):
    cpu = "cpu"
    gpu = "gpu"
    mpi = "mpi"


def get_isolves(solvers_api: osparc.SolversApi, latest: bool) -> list[osparc.Solver]:
    solvers: osparc.Solver = (
        solvers_api.list_solvers() if latest else solvers_api.list_solvers_releases()
    )

    return [s for s in solvers if "isolve" in s.title]


def is_type(solver: osparc.Solver, solver_type: ISolveType) -> bool:
    if solver_type == ISolveType.cpu:
        return (
            ISolveType.mpi.value not in solver.title
            and ISolveType.gpu.value not in solver.title
        )

    return solver_type.value in solver.title


def get_isolve(
    solvers_api: osparc.SolversApi, solver_type: ISolveType, version: str
) -> osparc.Solver:
    # finds the correct isolve version among all availables
    use_latest = version == "latest"
    isolves = get_isolves(solvers_api, use_latest)
    isolve = next(
        (
            solver
            for solver in isolves
            if (use_latest or solver.version == version)
            and is_type(solver, solver_type)
        ),
        None,
    )
    return isolve


def get_solver_type(sim: Simulation) -> ISolveType:
    run_type = sim.SolverSettings.RunType()
    if run_type in [SolverSettings.eRunType.kSerial, SolverSettings.eRunType.kShared]:
        return ISolveType.cpu
    if run_type in [
        SolverSettings.eRunType.kDistributed,
        SolverSettings.eRunType.kHybrid,
    ]:
        return ISolveType.mpi

    return ISolveType.gpu


def submit_simulation(
    solvers_api: osparc.SolversApi,
    files_api: osparc.FilesApi,
    sim: Simulation,
    solver_version: str,
    wait: bool | None = True,
) -> tuple[osparc.Job, osparc.JobStatus]:
    solver_type = get_solver_type(sim)
    solver: osparc.Solver = get_isolve(solvers_api, solver_type, version=solver_version)

    # the input file if not multiport
    if isinstance(sim, EmFdtdMultiportSimulation):
        raise NotImplementedError

    input_1: osparc.File = files_api.upload_file(file=sim.InputFileName(0))

    input_2 = None

    # parallelization
    nranks = ngpus = None
    if solver_type == ISolveType.mpi:
        nranks = sim.SolverSettings.NumberOfProcesses.Value
        input_2 = nranks
    elif solver_type == ISolveType.gpu:
        ngpus = sim.SolverSettings.NumberOfGpus.Value
        input_2 = ngpus

    job_inputs = {"input_1": input_1}
    if input_2 is not None:
        job_inputs.update({"input_2": input_2})

    job = solvers_api.create_job(
        solver_key=solver.id,
        version=solver.version,
        job_inputs=osparc.JobInputs(job_inputs),
    )

    status: osparc.JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)

    while not status.stopped_at:
        # For sim4life we can crate CJobProgressInfo and register the job in the taskmanager
        # However, I think the isolve Progress is not captured correctly in the sidecar.
        time.sleep(0.5)
        status: osparc.JobStatus = solvers_api.inspect_job(
            solver.id, solver.version, job.id
        )

        logger.info(f"Solver progress: {status.progress}/100")

    def get_results():
        outputs: osparc.JobOutputs = solvers_api.get_job_outputs(
            solver.id, solver.version, job.id
        )

        output_file = outputs.results["output_1"]
        log_file = outputs.results["output_2"]

        # move the output.h5 to the correct place with the correct filename
        if not output_file is None and isinstance(output_file, osparc.File):
            download_file_name: str = files_api.download_file(file_id=output_file.id)
            destination = sim.OutputFileName(0)
            shutil.move(download_file_name, destination)

        # move the log to the correct place with the correct filename
        # TODO: the axware logs will be extracted but not renamed. But then again, who needs them?
        if not log_file is None and isinstance(log_file, osparc.File):
            download_file_name: str = files_api.download_file(file_id=log_file.id)
            destination_path = Path(sim.OutputFileName(0)).parent
            with tarfile.open(download_file_name, "r") as tar:
                tar.extractall(destination_path)
                log_file = destination_path / "input.log"
                if log_file.exists():
                    destination_file = destination_path / str(
                        Path(sim.OutputFileName(0)).stem + ".log"
                    )
                    shutil.move(log_file, destination_file)

    logger.info(f"Solver finished with status: {status.state}")

    if status.state == "SUCCESS":
        get_results()

    return job, status


def run_simulation(
    sim: ApiSimulation,
    isolve_version: str | None = "latest",
    *,
    host: str = HOST,
    api_key: str | None = KEY,
    api_secret: str | None = SECRET,
):  # TODO: version should default to latest

    configuration = osparc.Configuration()
    configuration.host = host
    configuration.username = api_key
    configuration.password = api_secret

    with osparc.ApiClient(configuration) as api_client:

        solvers_api = osparc.SolversApi(api_client)
        files_api = osparc.FilesApi(api_client)

        _job, _status = submit_simulation(
            solvers_api, files_api, sim.raw, isolve_version, wait=True
        )

        logger.info(f"Simulation has results: {sim.HasResults()}")
        logger.info(
            f"Results have been written to: {Path(sim.GetOutputFileName()).parent}"
        )
