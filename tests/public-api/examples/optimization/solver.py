import json
import logging
import os
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import osparc
from osparc.api import FilesApi, SolversApi
from osparc.models import File, Job, JobInputs, JobOutputs, JobStatus, Solver


class OSparcServerException(Exception):
    pass


def handle_api_exceptions(osparc_server_exception):
    def decorator(method):
        def wrapper(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except osparc.exceptions.ApiException as e:
                args[0]._api_client.close()
                expt = json.loads(e.body)
                raise osparc_server_exception("\n".join(expt["errors"])) from None

        return wrapper

    return decorator


class OsparcSolver:
    """
    An oSparc solver
    """

    @handle_api_exceptions(OSparcServerException)
    def __init__(
        self, solver_key: str, solver_version: str, cfg: osparc.Configuration
    ) -> None:
        self._solver_key: str = solver_key
        self._solver_version: str = solver_version
        self._cfg: osparc.Configuration = cfg

        # APIs
        self._api_client = osparc.ApiClient(cfg)
        self._users_api = osparc.UsersApi(self._api_client)
        self._files_api = FilesApi(self._api_client)
        self._solvers_api = SolversApi(self._api_client)
        self._users_api.get_my_profile()  # validate access

        self._solver: Solver | None = None

        # Job dependent data
        self._job: Job | None = None
        self._status: JobStatus | None = None

    @handle_api_exceptions(OSparcServerException)
    def _generate_isolve_log(self) -> list[str]:
        """
        Unpacks the zip file containing iSolve logs and reads them in as a string
        """
        log_zip = Path(
            self._solvers_api.get_job_output_logfile(
                self._solver_key, self._solver_version, self._job.id
            )
        )
        log: list[str] = []
        with TemporaryDirectory() as tmp_dir:
            with zipfile.ZipFile(log_zip, "r") as zip_ref:
                zip_ref.extractall(tmp_dir)
            for pth in Path(tmp_dir).iterdir():
                if pth.is_file() and pth.name.endswith(".logs"):
                    with open(pth) as f:
                        log.append(f.read())
        os.remove(log_zip)
        return log

    @handle_api_exceptions(OSparcServerException)
    def submit_job(self, input_file: Path) -> None:
        """
        submit job to solver
        """
        # create objects
        input: File = self._files_api.upload_file(file=input_file)
        self._solver = self._solvers_api.get_solver_release(
            self._solver_key, self._solver_version
        )
        self._job = self._solvers_api.create_job(
            self._solver.id, self._solver.version, JobInputs({"input_1": input})
        )

        # solve
        logging.info(f"Start solving job: {self._job.id}")

        self._status = self._solvers_api.start_job(
            self._solver.id, self._solver.version, self._job.id
        )

    @handle_api_exceptions(OSparcServerException)
    def job_done(self) -> bool:
        """
        Check if a submitted job is done
        """
        if self._job is None:
            return True
        self._status = self._solvers_api.inspect_job(
            self._solver_key, self._solver_version, self._job.id
        )
        if self._status.stopped_at:
            if self._status.state != "SUCCESS":
                logging.error(
                    f"Failed job {self._job.id} with status {self._status.state}"
                )
                log: list[str] = [
                    f"Failed to solve job with status {self._status.state}",
                    "Server log:",
                ]
                log += self._generate_isolve_log()
                raise OSparcServerException("\n".join(log))
            return True
        else:
            return False

    @handle_api_exceptions(OSparcServerException)
    def fetch_results(self, output_file: Path, log_path: Path) -> None:
        """
        Fetches the results of a simulation
        """
        outputs: JobOutputs = self._solvers_api.get_job_outputs(
            self._solver_key, self._solver_version, self._job.id
        )
        for _, result in outputs.results.items():
            file = self._files_api.download_file(result.id)
            if result.filename == "output.h5":
                shutil.move(file, output_file)
            elif result.filename == "log.tgz":
                shutil.move(file, log_path)
            else:
                os.remove(file)
                logging.info(f"Received unexpected output: {result.filename}")
                continue
            logging.info(f"Successfully downloaded {result.filename}")

        self._job = None
        self._status = None
