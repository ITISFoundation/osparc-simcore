"""

 $ cd examples
 $ make install-ci
 $ make .env


Based on example https://github.com/nih-sparc/sparc-api/blob/v1.5.0/app/osparc.py
"""

import json
import os
from pathlib import Path
from time import sleep

import osparc
from dotenv import load_dotenv
from osparc.models import File, JobStatus

assert osparc.__version__ == "0.4.3"

# creates a fake config
config_path = Path("config.json")
config_path.write_text(
    json.dumps(
        {
            "simulation": {"Ending point": 3, "Point interval": 0.001},
            "output": ["Membrane/V"],
        }
    )
)


load_dotenv()
cfg = osparc.Configuration(
    host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
    username=os.environ["OSPARC_API_KEY"],
    password=os.environ["OSPARC_API_SECRET"],
)
print("Entrypoint", cfg.host)


with osparc.ApiClient(cfg) as api_client:
    # Upload our configuration file.

    files_api = osparc.FilesApi(api_client)

    config_file = files_api.upload_file(str(config_path))

    # Create our simulation.

    solvers_api = osparc.SolversApi(api_client)

    solver = solvers_api.get_solver_release("simcore/services/comp/opencor", "1.0.3")

    job = solvers_api.create_job(
        solver.id,
        solver.version,
        osparc.JobInputs(
            {
                "model_url": "https://models.physiomeproject.org/e/611/HumanSAN_Fabbri_Fantini_Wilders_Severi_2017.cellml",
                "config_file": config_file,
            }
        ),
    )
    print("Job created", job)

    # Start our simulation.

    status = solvers_api.start_job(solver.id, solver.version, job.id)

    # Check the status of our simulation until it has completed.

    while True:
        status = solvers_api.inspect_job(solver.id, solver.version, job.id)

        print(f">>> Progress: {status.progress}%...", flush=True)

        if status.progress == 100:
            break

        sleep(1)

    # Retrieve our simulation outputs.

    print("---------------------------------------")
    last_status: JobStatus = solvers_api.inspect_job(solver.id, solver.version, job.id)
    print(">>> What is the status?", last_status)

    outputs = solvers_api.get_job_outputs(solver.id, solver.version, job.id)

    for output_name, result in outputs.results.items():
        print(f">>> {output_name} = {result}")

    # Retrieve our simulation results.

    print("---------------------------------------")

    results: File | None = outputs.results["output_1"]

    if results is None:
        print(
            "Can't retrieve our simulation results...?!",
            "Failed ?",
            last_status.state,
            "Finished ?",
            last_status.progress == 100 or not last_status.stopped_at,
        )
    else:
        # List all the files that are available.

        print("---------------------------------------")
        print(files_api.list_files())

        # Print out the id of our simulation results file (?).

        print("---------------------------------------")
        print(">>> ", results.id)

        # Download our simulation results file (?).

        download_path: str = files_api.download_file(results.id)
        print("Downloaded to", download_path)
        print("Results:", Path(download_path).read_text()[:100])
