# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812
from models_library.api_schemas_directorv2.comp_tasks import TasksOutputs
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_fake_ports_data import (
    PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA,
)
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.client import long_running_task_request
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.director_v2.settings import (
    DirectorV2Settings,
    get_plugin_settings,
)
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL


@pytest.fixture
def fake_project(
    fake_project: ProjectDict, workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.fixture
def mock_directorv2_service_api_responses(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> AioResponsesMock:
    assert client.app
    settings: DirectorV2Settings = get_plugin_settings(client.app)

    url_pattern = rf"^{settings.base_url}.*?outputs:batchGet$"

    aioresponses_mocker.post(
        re.compile(url_pattern),
        payload=jsonable_encoder(
            TasksOutputs(
                nodes_outputs={
                    "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa": {
                        "output_1": {
                            "store": 0,
                            "path": "e08316a8-5afc-11ed-bab7-02420a00002b/08d15a6c-ae7b-4ea1-938e-4ce81a360ffa/single_number.txt",
                            "eTag": "1679091c5a880faf6fb5e6087eb1b2dc",
                        },
                        "output_2": 6,
                    },
                    "13220a1d-a569-49de-b375-904301af9295": {},
                }
            )
        ),
        repeat=True,
    )
    return aioresponses_mocker


@pytest.mark.acceptance_test()
@pytest.mark.parametrize(
    "user_role,expected",
    [
        pytest.param(UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *(pytest.param(r, status.HTTP_200_OK) for r in UserRole if r >= UserRole.GUEST),
    ],
)
async def test_io_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mock_catalog_service_api_responses: None,
    mock_directorv2_service_api_responses: AioResponsesMock,
    expected: HTTPStatus,
):
    """This tests implements a minimal workflow

    It later stage, this test might be split into smaller unit-tests
    """

    assert client.app

    project_id = user_project["uuid"]

    # list_project_metadata_ports
    expected_url = client.app.router["list_project_metadata_ports"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/metadata/ports") == expected_url

    resp = await client.get(f"/v0/projects/{project_id}/metadata/ports")
    ports_meta, error = await assert_status(resp, expected_status_code=expected)

    if not error:
        assert ports_meta == [
            {
                "key": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                "kind": "input",
                "content_schema": {
                    "description": "Input integer value",
                    "title": "X",
                    "type": "integer",
                },
            },
            {
                "key": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "kind": "input",
                "content_schema": {
                    "description": "Input integer value",
                    "title": "Z",
                    "type": "integer",
                },
            },
            {
                "key": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                "kind": "input",
                "content_schema": {
                    "description": "Input boolean value",
                    "title": "on",
                    "type": "boolean",
                },
            },
            {
                "key": "09fd512e-0768-44ca-81fa-0cecab74ec1a",
                "kind": "output",
                "content_schema": {
                    "description": "Output integer value",
                    "title": "Random sleep interval_2",
                    "type": "integer",
                },
            },
            {
                "key": "76f607b4-8761-4f96-824d-cab670bc45f5",
                "kind": "output",
                "content_schema": {
                    "description": "Output integer value",
                    "title": "Random sleep interval",
                    "type": "integer",
                },
            },
        ]

        assert ports_meta == PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA

    # get_project_inputs
    expected_url = client.app.router["get_project_inputs"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/inputs") == expected_url

    resp = await client.get(f"/v0/projects/{project_id}/inputs")
    project_inputs, error = await assert_status(resp, expected_status_code=expected)

    if not error:
        assert project_inputs == {
            "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
                "key": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                "value": 43,
                "label": "X",
            },
            "fc48252a-9dbb-4e07-bf9a-7af65a18f612": {
                "key": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "value": 1,
                "label": "Z",
            },
            "7bf0741f-bae4-410b-b662-fc34b47c27c9": {
                "key": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                "value": False,
                "label": "on",
            },
        }

    # update_project_inputs
    expected_url = client.app.router["update_project_inputs"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/inputs") == expected_url

    resp = await client.patch(
        f"/v0/projects/{project_id}/inputs",
        json=[{"key": "38a0d401-af4b-4ea7-ab4c-5005c712a546", "value": 42}],
    )
    project_inputs, error = await assert_status(resp, expected_status_code=expected)

    if not error:
        assert project_inputs == {
            "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
                "key": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                "value": 42,  # <---- updated
                "label": "X",
            },
            "fc48252a-9dbb-4e07-bf9a-7af65a18f612": {
                "key": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "value": 1,
                "label": "Z",
            },
            "7bf0741f-bae4-410b-b662-fc34b47c27c9": {
                "key": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                "value": False,
                "label": "on",
            },
        }

    # get_project_outputs (actual data)
    expected_url = client.app.router["get_project_outputs"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/outputs") == expected_url

    resp = await client.get(f"/v0/projects/{project_id}/outputs")
    project_outputs, error = await assert_status(resp, expected_status_code=expected)

    if not error:
        assert project_outputs == {
            "09fd512e-0768-44ca-81fa-0cecab74ec1a": {
                "key": "09fd512e-0768-44ca-81fa-0cecab74ec1a",
                "value": None,  # <---- was not computed!
                "label": "Random sleep interval_2",
            },
            "76f607b4-8761-4f96-824d-cab670bc45f5": {
                "key": "76f607b4-8761-4f96-824d-cab670bc45f5",
                "value": 6,  #
                "label": "Random sleep interval",
            },
        }


@pytest.mark.parametrize(
    "user_role",
    [UserRole.USER],
)
async def test_clone_project_and_set_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    # mocks backend
    storage_subsystem_mock: MockedStorageSubsystem,
    mock_catalog_service_api_responses: None,
    project_db_cleaner: None,
):
    #
    # NOTE: this is part of the workflow necessary to create study-jobs
    #
    assert client.app

    parent_project_id = user_project["uuid"]

    # - clone project_id -> project_clone_id ----------------------------------------------
    url = client.app.router["clone_project"].url_for(project_id=parent_project_id)
    assert f"/v0/projects/{parent_project_id}:clone" == url.path

    data = None

    async for long_running_task in long_running_task_request(
        client.session, url=client.make_url(url.path), json=None, client_timeout=30
    ):
        print(f"{long_running_task.progress=}")
        if long_running_task.done():
            data = await long_running_task.result()

    assert data is not None
    cloned_project = ProjectGet.model_validate(data)

    assert parent_project_id != cloned_project.uuid
    assert user_project["description"] == cloned_project.description
    assert TypeAdapter(datetime).validate_python(
        user_project["creationDate"]
    ) < TypeAdapter(datetime).validate_python(cloned_project.creation_date)

    # - set_inputs project_clone_id ----------------------------------------------
    job_inputs_values = {"X": 42}  # like JobInputs.values

    url = client.app.router["get_project_inputs"].url_for(
        project_id=f"{cloned_project.uuid}"
    )
    assert f"/v0/projects/{cloned_project.uuid}/inputs" == url.path

    response = await client.get(url.path)
    project_inputs, _ = await assert_status(
        response, expected_status_code=status.HTTP_200_OK
    )

    # Emulates transformation between JobInputs.values and body format which relies on keys
    update_inputs = []
    for label, value in job_inputs_values.items():
        # raise StopIteration if label not found!
        found_input = next(p for p in project_inputs.values() if p["label"] == label)
        if found_input["value"] != value:  # only patch if value changed
            update_inputs.append({"key": found_input["key"], "value": value})

    assert (
        client.app.router["update_project_inputs"].url_for(
            project_id=f"{cloned_project.uuid}"
        )
        == url
    )
    response = await client.patch(url.path, json=update_inputs)
    project_inputs, _ = await assert_status(
        response, expected_status_code=status.HTTP_200_OK
    )
    assert (
        next(p for p in project_inputs.values() if p["label"] == "X")["value"]
        == job_inputs_values["X"]
    )
