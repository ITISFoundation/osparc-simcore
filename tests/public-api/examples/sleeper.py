"""

 $ cd examples
 $ make install-ci
 $ make .env

"""

import os
import time
from pathlib import Path

import osparc
from dotenv import load_dotenv
from osparc import UsersApi
from osparc.api import FilesApi, SolversApi
from osparc.models import File, Job, JobInputs, JobOutputs, JobStatus, Solver

assert osparc.__version__ == "0.4.3"

Path("file_with_number.txt").write_text("3")


load_dotenv()

cfg = osparc.Configuration(
    host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
    username=os.environ["OSPARC_API_KEY"],
    password=os.environ["OSPARC_API_SECRET"],
)
print(cfg.host)

with osparc.ApiClient(cfg) as api_client:

    profile = UsersApi(api_client).get_my_profile()
    print(profile)
    #
    #  {'first_name': 'foo',
    #  'gravatar_id': 'aa33fssec77ea434c2ea4fb92d0fd379e',
    #  'groups': {'all': {'description': 'all users',
    #                     'gid': '1',
    #                     'label': 'Everyone'},
    #             'me': {'description': 'primary group',
    #                    'gid': '2',
    #                    'label': 'foo'},
    #             'organizations': []},
    #  'last_name': '',
    #  'login': 'foo@itis.swiss',
    #  'role': 'USER'}
    #

    files_api = FilesApi(api_client)
    input_file: File = files_api.upload_file(file="file_with_number.txt")

    solvers_api = SolversApi(api_client)
    solver: Solver = solvers_api.get_solver_release(
        "simcore/services/comp/itis/sleeper", "2.0.2"
    )

    job: Job = solvers_api.create_job(
        solver.id,
        solver.version,
        JobInputs(
            {
                "input_3": False,  # If true, service will fail after sleep
                "input_2": 3.0,  # Amount of time-sleep
                "input_1": input_file,  # File containing only one integer
            }
        ),
    )

    status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
    while not status.stopped_at:
        time.sleep(3)
        status = solvers_api.inspect_job(solver.id, solver.version, job.id)
        print("Solver progress", f"{status.progress}/100", flush=True)
    #
    # Solver progress 0/100
    # Solver progress 100/100

    outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)

    print(f"Job {outputs.job_id} got these results:")
    for output_name, result in outputs.results.items():
        print(output_name, "=", result)

    #
    # Job 19fc28f7-46fb-4e96-9129-5e924801f088 got these results:
    #
    # output_1 = {'checksum': '859fda0cb82fc4acb4686510a172d9a9-1',
    # 'content_type': 'text/plain',
    # 'filename': 'single_number.txt',
    # 'id': '9fb4f70e-3589-3e9e-991e-3059086c3aae'}
    # output_2 = 4.0

    download_path: str = files_api.download_file(file_id=outputs.results["output_1"].id)
    print(Path(download_path).read_text())
    #
    # 7
