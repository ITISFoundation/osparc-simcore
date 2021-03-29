# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

from models_library.projects_nodes import Inputs, InputTypes, SimCoreFileLink
from models_library.projects_nodes_io import NodeID
from pydantic import create_model
from simcore_service_api_server.models.schemas.files import File
from simcore_service_api_server.models.schemas.jobs import ArgumentType, Job, JobInputs
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.utils.solver_job_models_converters import (
    create_job_inputs_from_node_inputs,
    create_node_inputs_from_job_inputs,
    create_project_from_job,
    get_args,
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
    createproject_body = create_project_from_job(solver, job, inputs)

    assert createproject_body.uuid == job.id


def test_job_to_node_inputs_conversion():
    # TODO: add here service input schemas and cast correctly?

    # Two equivalent inputs
    job_inputs = JobInputs(
        values={
            "x": 4.33,
            "n": 55,
            "title": "Temperature",
            "enabled": True,
            "input_file": File(
                filename="input.txt",
                id="0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
                checksum="859fda0cb82fc4acb4686510a172d9a9-1",
            ),
        }
    )
    for name, value in job_inputs.values.items():
        assert isinstance(value, get_args(ArgumentType)), f"Invalid type in {name}"

    node_inputs: Inputs = {
        "x": 4.33,
        "n": 55,
        "title": "Temperature",
        "enabled": True,
        "input_file": SimCoreFileLink(
            path="api/0a3b2c56-dbcd-4871-b93b-d454b7883f9f/input.txt",
            eTag="859fda0cb82fc4acb4686510a172d9a9-1",
            label="input.txt",
        ),
    }

    for name, value in node_inputs.items():
        # TODO: py3.8 use typings.get_args
        assert isinstance(value, get_args(InputTypes)), f"Invalid type in {name}"

    # test transformations in both directions
    got_node_inputs = create_node_inputs_from_job_inputs(inputs=job_inputs)
    got_job_inputs = create_job_inputs_from_node_inputs(inputs=node_inputs)

    NodeInputs = create_model("NodeInputs", __root__=(Dict[str, InputTypes], ...))
    print(NodeInputs.parse_obj(got_node_inputs).json(indent=2))
    print(got_job_inputs.json(indent=2))

    assert got_job_inputs == job_inputs
    assert got_node_inputs == node_inputs
