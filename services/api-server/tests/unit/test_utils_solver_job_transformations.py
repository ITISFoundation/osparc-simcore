# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from simcore_service_api_server.models.schemas.jobs import Job, JobInputs
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.utils.solver_job_transformations import (
    create_project_model_for_job,
)


def test_create_project_model_for_job():
    solver = Solver.parse_obj(
        {
            "id": "simcore/services/comp/itis/sleeper",
            "version": "2.0.2",
            "title": "sleeper",
            "description": "A service which awaits for time to pass.",
            "maintainer": "info@itis.swiss",
            "url": "http://127.0.0.1:8006/v0/solvers/simcore/services/comp/itis/sleeper/releases/2.0.2",
        }
    )

    inputs = JobInputs.parse_obj(
        {
            "values": {
                "input_3": False,  # Fail after sleep ?
                "input_2": 3,  # sleep interval (secs)
                "input_1": {
                    "id": "e2335f87-6cf9-3148-87d4-262901403621",
                    "filename": "file_with_number.txt",
                    "content_type": "text/plain",
                    "checksum": "9fdfbdb9686b3391bbea7c9e74aba49e-1",
                },
            }
        }
    )

    print(inputs.json(indent=2))

    job = Job.create_from_solver(solver.id, solver.version, inputs)

    # body of create project!
    createproject_body = create_project_model_for_job(solver, job, inputs)

    assert createproject_body.uuid == job.id
