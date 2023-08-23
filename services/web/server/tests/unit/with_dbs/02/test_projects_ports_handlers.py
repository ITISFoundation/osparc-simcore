# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPOk
from models_library.api_schemas_long_running_tasks.tasks import TaskStatus
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from pydantic import parse_obj_as
from pytest_simcore.helpers.faker_webserver import (
    PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA,
)
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_webserver_unit_with_db import MockedStorageSubsystem
from servicelib.aiohttp.long_running_tasks.client import long_running_task_request
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from tenacity import TryAgain, retry
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL


@pytest.fixture
def fake_project(
    fake_project: ProjectDict, workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.mark.acceptance_test()
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_io_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mock_catalog_service_api_responses: None,
    expected: type[web.HTTPException],
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
    ports_meta, error = await assert_status(resp, expected_cls=expected)

    if not error:
        assert ports_meta == [
            {
                "key": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                "kind": "input",
                "content_schema": {
                    "description": "Parameter of type integer",
                    "title": "X",
                    "type": "integer",
                },
            },
            {
                "key": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "kind": "input",
                "content_schema": {
                    "description": "Parameter of type integer",
                    "title": "Z",
                    "type": "integer",
                },
            },
            {
                "key": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                "kind": "input",
                "content_schema": {
                    "description": "Parameter of type boolean",
                    "title": "on",
                    "type": "boolean",
                },
            },
            {
                "key": "09fd512e-0768-44ca-81fa-0cecab74ec1a",
                "kind": "output",
                "content_schema": {
                    "default": 0,
                    "description": "Captures integer values attached to it",
                    "title": "Random sleep interval_2",
                    "type": "integer",
                },
            },
            {
                "key": "76f607b4-8761-4f96-824d-cab670bc45f5",
                "kind": "output",
                "content_schema": {
                    "default": 0,
                    "description": "Captures integer values attached to it",
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
    project_inputs, error = await assert_status(resp, expected_cls=expected)

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
    project_inputs, error = await assert_status(resp, expected_cls=expected)

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
    project_outputs, error = await assert_status(resp, expected_cls=expected)

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


@retry(
    wait=wait_fixed(0.5),
    stop=stop_after_delay(60),
    reraise=True,
)
async def _wait_until_project_cloned_or_timeout(
    client: TestClient, status_url: str, result_url: str
) -> ProjectGet:
    # GET task status now until done
    response = await client.get(status_url)
    response.raise_for_status()
    task_status = Envelope[TaskStatus].parse_obj(await response.json()).data
    assert task_status

    if not task_status.done:
        msg = "Timed out creating project. TIP: Try again, or contact oSparc support if this is happening repeatedly"
        raise TryAgain(msg)

    response = await client.get(result_url)
    response.raise_for_status()
    task_result = Envelope[ProjectGet].parse_obj(await response.json()).data
    assert task_result
    return task_result


@pytest.mark.xfail(reason="Under dev")
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
    cloned_project = ProjectGet.parse_obj(data)

    assert parent_project_id != cloned_project.uuid
    assert user_project["description"] == cloned_project.description
    assert parse_obj_as(datetime, user_project["creationDate"]) < parse_obj_as(
        datetime, cloned_project.creation_date
    )

    # - set_inputs project_clone_id ----------------------------------------------
    job_inputs_values = {"X": 42}  # like JobInputs.values

    url = client.app.router["get_project_inputs"].url_for(
        project_id=f"{cloned_project.uuid}"
    )
    assert f"/v0/projects/{cloned_project.uuid}/inputs" == url.path

    response = await client.get(url.path)
    project_inputs, _ = await assert_status(response, expected_cls=HTTPOk)

    # Emulates transformation between JobInputs.values and body format which relies on keys
    body = []
    for label, value in job_inputs_values.items():
        # raise StopIteration if label not found!
        selected_input = next(p for p in project_inputs if p["label"] == label)
        if selected_input["value"] != value:  # only patch if value changed
            body.append({"key": selected_input["key"], "value": value})

    assert (
        client.app.router["update_project_inputs"].url_for(
            project_id=f"{cloned_project.uuid}"
        )
        == url
    )
    response = await client.patch(url.path, json=body)
    project_inputs, _ = await assert_status(response, expected_cls=HTTPOk)
    assert (
        project_inputs["38a0d401-af4b-4ea7-ab4c-5005c712a546"]["value"]
        == job_inputs_values["X"]
    )

    # - run project_clone_id
    #    - raise if error
    #    - print progress
    #    - stop if f cancelled
    # - get_outputs project_clone_id
    #    - raise if error
    # - soft_delete project_clone_id
