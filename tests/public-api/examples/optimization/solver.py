import os
import time
from pathlib import Path
from tqdm import tqdm
import shutil
import json
import logging
import zipfile
from tempfile import TemporaryDirectory
from typing import Optional, List

import osparc
from osparc.models import File, Solver, Job, JobStatus, JobInputs, JobOutputs
from osparc.api import FilesApi, SolversApi


logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] %(message)s')

class OsparcSolver():
    """
    An oSparc solver
    """
    def __init__(self, solver_key: str, solver_version: str, cfg: osparc.Configuration):

        self._solver_key: str = solver_key
        self._solver_version: str = solver_version
        self._cfg: osparc.Configuration = cfg

        # APIs
        try:
            self._api_client = osparc.ApiClient(cfg)
            self._users_api = osparc.UsersApi(self._api_client)
            self._files_api = FilesApi(self._api_client)
            self._solvers_api = SolversApi(self._api_client)
            self._users_api.get_my_profile() # validate access
        except osparc.exceptions.ApiException as e:
            self._api_client.close()
            expt = json.loads(e.body)
            raise Exception('\n'.join(expt["errors"])) from None
        
        self._solver: Optional[Solver] = None

        # Job dependent data
        self._job: Optional[Job] = None
        self._status: Optional[JobStatus] = None

    def _generate_isolve_log(self) -> List[str]:
        """
        Unpacks the zip file containing iSolve logs and reads them in as a string
        """
        log_zip = Path(self._solvers_api.get_job_output_logfile(self._solver_key, self._solver_version, self._job.id))
        log: List[str] = []
        with TemporaryDirectory() as tmp_dir:
            with zipfile.ZipFile(log_zip, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)
            for pth in Path(tmp_dir).iterdir():
                if pth.is_file() and pth.name.endswith('.logs'):
                    with open(pth, "r") as f:
                        log.append(f.read())
        os.remove(log_zip)
        return log

    def submit_job(self, input_file: Path):
        """
        submit job to solver
        """
        try:
            # create objects
            input: File = self._files_api.upload_file(file=input_file)
            self._solver = self._solvers_api.get_solver_release(self._solver_key, self._solver_version)
            self._job = self._solvers_api.create_job( self._solver.id, self._solver.version, JobInputs({"input_1": input}))

            # solve
            logging.info(f'Start solving job: {self._job.id}')

            self._status = self._solvers_api.start_job(self._solver.id, self._solver.version, self._job.id)
        except osparc.exceptions.ApiException as e:
            self._api_client.close()
            expt = json.loads(e.body)
            raise Exception('\n'.join(expt["errors"])) from None
                
    def job_done(self) -> bool:
        """
        Check if a submitted job is done
        """
        try:
            if self._job is None:
                return True
            self._status = self._solvers_api.inspect_job(self._solver_key, self._solver_version, self._job.id)
            if self._status.stopped_at:
                if self._status.state != 'SUCCESS':
                    logging.error(f'Failed job {self._job.id} with status {self._status.state}')
                    log: List[str] = [f'Failed to solve job with status {self._status.state}', 'Server log:']
                    log += self._generate_isolve_log()
                    raise Exception('\n'.join(log))
                return True
            else:
                return False
        except osparc.exceptions.ApiException as e:
            self._api_client.close()
            expt = json.loads(e.body)
            raise Exception('\n'.join(expt["errors"])) from None           
        
    def fetch_results(self, output_file: Path, log_path: Path) -> bool:
        """
        Fetches the results of a simulation
        """
        try:
            outputs: JobOutputs = self._solvers_api.get_job_outputs(self._solver_key, self._solver_version, self._job.id)
            for _, result in outputs.results.items():
                file = self._files_api.download_file(result.id)
                if result.filename == 'output.h5':
                    shutil.move(file, output_file)
                elif result.filename == 'log.tgz':
                    shutil.move(file, log_path)
                else:
                    os.remove(file)
                    logging.info(f'Received unexpected output: {result.filename}')
                    continue
                logging.info(f'Successfully downloaded {result.filename}')
                
            self._job = None
            self._status = None
        except osparc.exceptions.ApiException as e:
            self._api_client.close()
            expt = json.loads(e.body)
            raise Exception('\n'.join(expt["errors"])) from None



def call_osparc_solver(solver_key: str, solver_version: str, input_file: Path, output_file: Path, log_path: Path, cfg: Optional[osparc.Configuration] = None) -> None:
    """
    Call a solver on osparc
    """
    if cfg is None:
        cfg = get_config()
    assert input_file.name.endswith('.h5'), f'{str(input_file)} must be a h5 file'
    try:
        with osparc.ApiClient(cfg) as api_client:
            # APIs
            users_api = osparc.UsersApi(api_client)
            files_api = FilesApi(api_client)
            solvers_api = SolversApi(api_client)
            users_api.get_my_profile() # validate access

            # create objects
            input: File = files_api.upload_file(file=input_file)
            solver: Solver = solvers_api.get_solver_release(solver_key, solver_version)
            job: Job = solvers_api.create_job( solver.id, solver.version, JobInputs({"input_1": input}))
            logging.info(f'Done creating job using input file: {input_file}')

            # solve
            logging.info(f'Start solving job: {job.id}')
            status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
            with tqdm(total=100) as bar:
                while not status.stopped_at:
                    time.sleep(0.5)
                    status = solvers_api.inspect_job(solver.id, solver.version, job.id)
                    bar.update(status.progress)
            if status.state != 'SUCCESS':
                logging.error(f'Failed job {job.id} with status {status.state}')
                log: List[str] = [f'Failed to solve job with status {status.state}', 'Server log:']
                log.append( generate_isolve_log(solvers_api, solver_key, solver_version, job.id) )
                raise Exception('\n'.join(log))
            logging.info(f'Successfully solved job: {job.id}')

            # download outputs
            outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)
            for _, result in outputs.results.items():
                file = files_api.download_file(result.id)
                if result.filename == 'output.h5':
                    shutil.move(file, output_file)
                elif result.filename == 'log.tgz':
                    shutil.move(file, log_path)
                else:
                    logging.info(f'Received unexpected output: {result.filename}')
                    continue
                logging.info(f'Successfully downloaded {result.filename}')

    except osparc.exceptions.ApiException as e:
        api_client.close()
        expt = json.loads(e.body)
        raise Exception('\n'.join(expt["errors"])) from None


if __name__ == '__main__':
    cfg = osparc.Configuration(
        username="1c9034e8-713c-5bec-b0ce-6aa070e1b329",
        password="a1724945-1f91-5dca-8a0c-8efb018028b0"
    )
    solver_key: str = "simcore/services/comp/isolve"
    solver_version: str = "2.1.16"
    project: Path = Path(os.getcwd()) / 'project'
    call_osparc_solver(solver_key, solver_version, project/'input.h5', project/'output.h5', project/'log.tgz', cfg)