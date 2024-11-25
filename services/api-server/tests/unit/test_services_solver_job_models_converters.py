# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from faker import Faker
from models_library.projects import Project
from models_library.projects_nodes import InputsDict, InputTypes, SimCoreFileLink
from pydantic import RootModel, TypeAdapter, create_model
from simcore_service_api_server.models.schemas.files import File
from simcore_service_api_server.models.schemas.jobs import ArgumentTypes, Job, JobInputs
from simcore_service_api_server.models.schemas.solvers import Solver
from simcore_service_api_server.services.solver_job_models_converters import (
    create_job_from_project,
    create_job_inputs_from_node_inputs,
    create_jobstatus_from_task,
    create_new_project_for_job,
    create_node_inputs_from_job_inputs,
)


def test_create_project_model_for_job(faker: Faker):
    solver = Solver.model_validate(
        {
            "id": "simcore/services/comp/itis/sleeper",
            "version": "2.0.2",
            "title": "sleeper",
            "description": "A service which awaits for time to pass.",
            "maintainer": "info@itis.swiss",
            "url": "http://127.0.0.1:8006/v0/solvers/simcore/services/comp/itis/sleeper/releases/2.0.2",
        }
    )

    inputs = JobInputs.model_validate(
        {
            "values": {
                "input_3": False,  # Fail after sleep ?
                "input_2": 3,  # sleep interval (secs)
                "input_1": {
                    "id": "e2335f87-6cf9-3148-87d4-262901403621",
                    "filename": "file_with_number.txt",
                    "content_type": "text/plain",
                    "checksum": faker.sha256(),
                },
            }
        }
    )

    print(inputs.model_dump_json(indent=2))

    job = Job.create_solver_job(solver=solver, inputs=inputs)

    # body of create project!
    createproject_body = create_new_project_for_job(solver, job, inputs)

    # ensures one-to-one relation
    assert createproject_body.uuid == job.id
    assert createproject_body.name == job.name


def test_job_to_node_inputs_conversion():
    # TODO: add here service input schemas and cast correctly?

    # Two equivalent inputs
    job_inputs = JobInputs(
        values={
            "x": 4.33,
            "n": 55,
            "title": "Temperature",
            "enabled": True,
            "some_list": [1, 2, "foo"],
            "input_file": File(
                filename="input.txt",
                id="0a3b2c56-dbcd-4871-b93b-d454b7883f9f",
                e_tag="859fda0cb82fc4acb4686510a172d9a9-1",
            ),
        }
    )
    for value in job_inputs.values.values():
        assert TypeAdapter(ArgumentTypes).validate_python(value) == value

    node_inputs: InputsDict = {
        "x": 4.33,
        "n": 55,
        "title": "Temperature",
        "enabled": True,
        "some_list": [1, 2, "foo"],
        "input_file": SimCoreFileLink(
            store=0,
            path="api/0a3b2c56-dbcd-4871-b93b-d454b7883f9f/input.txt",
            eTag="859fda0cb82fc4acb4686510a172d9a9-1",
            label="input.txt",
        ),
    }

    for value in node_inputs.values():
        assert TypeAdapter(InputTypes).validate_python(value) == value

    # test transformations in both directions
    got_node_inputs = create_node_inputs_from_job_inputs(inputs=job_inputs)
    got_job_inputs = create_job_inputs_from_node_inputs(inputs=node_inputs)

    NodeInputs = create_model("NodeInputs", __base__=RootModel[dict[str, InputTypes]])
    print(NodeInputs.model_validate(got_node_inputs).model_dump_json(indent=2))
    print(got_job_inputs.model_dump_json(indent=2))

    assert got_job_inputs == job_inputs
    assert got_node_inputs == node_inputs


def test_create_job_from_project(faker: Faker):
    project = Project.model_validate(
        {
            "uuid": "f925e30f-19de-42dc-acab-3ce93ea0a0a7",
            "name": "simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/2.0.2/jobs/f925e30f-19de-42dc-acab-3ce93ea0a0a7",
            "description": 'Study associated to solver job:\n{\n  "id": "f925e30f-19de-42dc-acab-3ce93ea0a0a7",\n  "name": "simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/2.0.2/jobs/f925e30f-19de-42dc-acab-3ce93ea0a0a7",\n  "inputs_checksum": "aac0bb28285d6e5918121630fa8c368130c6b05f80fd9622760078608fc44e96",\n  "created_at": "2021-03-26T10:43:27.828975"\n}',
            "thumbnail": "https://2xx2gy2ovf3r21jclkjio3x8-wpengine.netdna-ssl.com/wp-content/uploads/2018/12/API-Examples.jpg",
            "prjOwner": "foo@itis.swiss",
            "creationDate": "2021-03-26T10:43:27.867Z",
            "lastChangeDate": "2021-03-26T10:43:33.595Z",
            "workbench": {
                "e694de0b-2e91-5be7-9319-d89404170991": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.2",
                    "label": "sleeper",
                    "progress": 100,
                    "thumbnail": None,
                    "runHash": "1c4e09777dbf6fb1ab4bfb02f8e62c7b6fc07393d8c880d5762a86afeddb30b5",
                    "inputs": {
                        "input_3": 0,
                        "input_2": 3,
                        "input_1": {
                            "store": 0,
                            "path": "api/bfb821c0-a4ef-305e-a23b-4d79065f0078/file_with_number.txt",
                            "eTag": None,
                            "label": "file_with_number.txt",
                        },
                    },
                    "inputAccess": None,
                    "inputNodes": [],
                    "outputs": {
                        "output_1": {
                            "store": 0,
                            "path": "f925e30f-19de-42dc-acab-3ce93ea0a0a7/e694de0b-2e91-5be7-9319-d89404170991/single_number.txt",
                            "eTag": "6c22e9b968b205c0dd3614edd1b28d35-1",
                        },
                        "output_2": 1,
                    },
                    "outputNode": None,
                    "outputNodes": None,
                    "parent": None,
                    "position": None,
                    "state": {
                        "currentStatus": "SUCCESS",
                        "modified": False,
                        "dependencies": [],
                    },
                }
            },
            "accessRights": {"2": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "classifiers": [],
            "ui": {
                "slideshow": {},
                "workbench": {
                    "e694de0b-2e91-5be7-9319-d89404170991": {
                        "position": {"x": 633, "y": 229}
                    }
                },
                "currentNodeId": "e694de0b-2e91-5be7-9319-d89404170991",
            },
            "quality": {},
            "tags": [],
            "state": {
                "locked": {
                    "value": False,
                    "status": "CLOSED",
                },
                "state": {"value": "SUCCESS"},
            },
        },
    )

    expected_job = Job.model_validate(
        {
            "id": "f925e30f-19de-42dc-acab-3ce93ea0a0a7",
            "name": "simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/2.0.2/jobs/f925e30f-19de-42dc-acab-3ce93ea0a0a7",
            "created_at": "2021-03-26T10:43:27.867Z",
            "runner_name": "solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.0.2",
            "inputs_checksum": "a887dfcac17f6e6045139ec00fbb3038a450111fdc8e10e94d66590f33b3f10e",
            "url": None,
            "runner_url": None,
            "outputs_url": None,
        }
    )

    solver_key = "simcore/services/comp/itis/sleeper"
    solver_version = "2.0.2"

    def fake_url_for(*args, **kwargs):
        return faker.url()

    job = create_job_from_project(
        solver_key, solver_version, project, url_for=fake_url_for
    )

    assert job.id == project.uuid
    assert job.name == project.name

    url_field_names = {name for name in job.model_fields if name.endswith("url")}
    assert all(getattr(job, _) for _ in url_field_names)

    # this tends to be a problem
    assert job.inputs_checksum == expected_job.inputs_checksum
    assert job.model_dump(exclude=url_field_names) == expected_job.model_dump(
        exclude=url_field_names
    )


@pytest.mark.skip(reason="TODO: next PR")
def test_create_jobstatus_from_task():
    from simcore_service_api_server.models.schemas.jobs import JobStatus
    from simcore_service_api_server.services.director_v2 import ComputationTaskGet

    task = ComputationTaskGet.model_validate({})  # TODO:
    job_status: JobStatus = create_jobstatus_from_task(task)

    assert job_status.job_id == task.id

    # TODO: activate
    # #frozen = True
    # #allow_mutation = False
    # and remove take_snapshot by generating A NEW JobStatus!
