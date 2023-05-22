import os
import time

import osparc
from dotenv import load_dotenv
from osparc.api import SolversApi
from osparc.models import Job, JobInputs, JobOutputs, JobStatus, Solver


def load_config():
    load_dotenv()
    cfg = osparc.Configuration(
        host=os.environ.get("OSPARC_API_URL", "http://127.0.0.1:8006"),
        username=os.environ["OSPARC_API_KEY"],
        password=os.environ["OSPARC_API_SECRET"],
    )
    print("Entrypoint", cfg.host)
    return cfg


def rsinc(x: list[float], a: float = 3.14) -> float:
    cfg = load_config()
    with osparc.ApiClient(cfg) as api_client:

        solvers_api = SolversApi(api_client)
        solver: Solver = solvers_api.get_solver_release(
            "simcore/services/comp/cctest-sinc", "0.1.0"
        )

        job: Job = solvers_api.create_job(
            solver.id,
            solver.version,
            JobInputs(
                {
                    "x": x,
                    "a": float(a),
                }
            ),
        )

        status: JobStatus = solvers_api.start_job(solver.id, solver.version, job.id)
        while not status.stopped_at:
            time.sleep(1)
            status = solvers_api.inspect_job(solver.id, solver.version, job.id)
            print("Solver progress", f"{status.progress}/100", flush=True)

        outputs: JobOutputs = solvers_api.get_job_outputs(
            solver.id, solver.version, job.id
        )

        print(f"Job {outputs.job_id} got these results:")
        for output_name, result in outputs.results.items():
            print(output_name, "=", result)

        return outputs.results["out_1"]


if __name__ == "__main__":

    rsinc([1.0, 2.0, 3.0], a=3.14)
