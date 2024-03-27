"""
Multi-scale rabbit cardiac electrophysiology models
Rabbit Soltis-Saucerman model with full b-AR signalling (Rabbit SS 1D cardiac)

 $ cd examples
 $ make install-ci
 $ make .env

SEE https://sparc.science/datasets/4?type=dataset
"""

import os
import sys
import time
from pathlib import Path
from time import sleep

import osparc
from dotenv import load_dotenv
from osparc.models import File, JobStatus

assert osparc.__version__ == "0.4.3"

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
data_dir = current_dir / "data_rabbit_cardiac"

load_dotenv()
cfg = osparc.Configuration(
    host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
    username=os.environ["OSPARC_API_KEY"],
    password=os.environ["OSPARC_API_SECRET"],
)
print("Entrypoint", cfg.host)


with osparc.ApiClient(cfg) as api_client:
    # Upload init states file.

    files_api = osparc.FilesApi(api_client)
    initial_wtstates_file = files_api.upload_file(
        str(data_dir / "initial_WTstates.txt")
    )

    # Create our simulation.

    solvers_api = osparc.SolversApi(api_client)

    solver = solvers_api.get_solver_release(
        "simcore/services/comp/rabbit-ss-1d-cardiac-model", "1.0.0"
    )

    # SEE data_rabbit_cardiac/ss1d_meta.json::inputs
    job = solvers_api.create_job(
        solver.id,
        solver.version,
        osparc.JobInputs(
            {
                "Na": 0,
                "GKr": 1,
                "TotalSimulationTime": 50,
                "TargetHeartRatePhase1": 60,
                "TargetHeartRatePhase2": 150,
                "TargetHeartRatePhase3": 60,
                "cAMKII": "WT",
                "tissue_size_tw": 165,
                "tissue_size_tl": 165,
                "Homogeneity": "homogeneous",
                "num_threads": 4,
                "initialWTStates": initial_wtstates_file,
            }
        ),
    )
    print("Job created", job)

    # Start our simulation.
    status = solvers_api.start_job(solver.id, solver.version, job.id)
    start_t = time.perf_counter()

    # Check the status of our simulation until it has completed.
    while True:
        status = solvers_api.inspect_job(solver.id, solver.version, job.id)

        print(
            f">>> Progress: {status.progress}% ",
            f"[elapsed:{time.perf_counter() - start_t:4.2f}s]...",
            flush=True,
        )

        if status.progress == 100:
            break

        sleep(1)

    # Retrieve our simulation outputs.

    print("---------------------------------------")
    last_status: JobStatus = solvers_api.inspect_job(solver.id, solver.version, job.id)
    print(">>> What is the status?", last_status)

    outputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)

    # SEE data_rabbit_cardiac/ss1d_meta.json::outputs
    for output_name, result in outputs.results.items():
        print(f">>> {output_name} = {result}")

    # Retrieve our simulation results.

    print("---------------------------------------")
    result: File | None

    for output_name, result in outputs.results.items():
        if result is None:
            print(
                "Can't retrieve our simulation results {output_name}...?!",
                "Failed ?",
                last_status.state,
                "Finished ?",
                last_status.progress == 100 or not last_status.stopped_at,
            )
        else:

            # Print out the id of our simulation results file (?).

            print("---------------------------------------")
            print(">>> ", result.id)

            # Download our simulation results file (?).

            download_path: str = files_api.download_file(result.id)
            print("Downloaded to", download_path)
            print("Content-Type: ", result.content_type)
            if result.content_type == "text/plain":
                print("Result:", Path(download_path).read_text()[:100])
            print("Status: ", Path(download_path).stat())

    # List all the files that are available.
    print("---------------------------------------")
    print(files_api.list_files())
