import json
import os
import time
from pathlib import Path

import osparc
from osparc.api import FilesApi, SolversApi
from osparc.models import File, Job, JobInputs, JobOutputs, JobStatus, Solver

cfg = osparc.Configuration(**json.loads(Path("config.json").read_text()))


###-
with osparc.ApiClient(cfg) as api_client:

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
                "input_3": 0,
                "input_2": 3.0,
                "input_1": input_file,
            }
        ),
    )

    status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
    while not status.stopped_at:
        time.sleep(3)
        status = solvers_api.inspect_job(solver.id, solver.version, job.id)
        print("Solver progress", f"{status.progress}/100", flush=True)

    outputs: JobOutputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)

    print(f"Job {outputs.job_id} got these results:")
    for output_name, result in outputs.results.items():
        print(output_name, "=", result)
