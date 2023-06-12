# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects_nodes import Node, NodeID
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pydantic import parse_obj_as
from pytest_simcore.helpers.faker_webserver import (
    PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA,
)
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import _handlers_project_ports
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL


@pytest.mark.parametrize(
    "route",
    _handlers_project_ports.routes,
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_route_against_openapi_specs(route, openapi_specs: OpenApiSpecs):

    assert route.path.startswith(f"/{VX}")
    path = route.path.replace(f"/{VX}", "")

    assert path in openapi_specs.paths

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method=} for {path=} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"


@pytest.fixture
def workbench_db_column() -> dict[str, Any]:
    return {
        "13220a1d-a569-49de-b375-904301af9295": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper",
            "inputs": {
                "input_2": {
                    "nodeUuid": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                    "output": "out_1",
                },
                "input_3": False,
                "input_4": 0,
            },
            "inputsUnits": {},
            "inputNodes": ["38a0d401-af4b-4ea7-ab4c-5005c712a546"],
            "parent": None,
            "thumbnail": "",
        },
        "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "X",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 43},
            "runHash": None,
        },
        "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper_2",
            "inputs": {
                "input_2": 2,
                "input_3": {
                    "nodeUuid": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                    "output": "out_1",
                },
                "input_4": {
                    "nodeUuid": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                    "output": "out_1",
                },
            },
            "inputsUnits": {},
            "inputNodes": [
                "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "7bf0741f-bae4-410b-b662-fc34b47c27c9",
            ],
            "parent": None,
            "thumbnail": "",
            "state": {"currentStatus": "SUCCESS"},
            "progress": 100,
            "outputs": {
                "output_1": {
                    "store": 0,
                    "path": "e08316a8-5afc-11ed-bab7-02420a00002b/08d15a6c-ae7b-4ea1-938e-4ce81a360ffa/single_number.txt",
                    "eTag": "1679091c5a880faf6fb5e6087eb1b2dc",
                },
                "output_2": 6,
            },
            "runHash": "5d55ebe569aa0abeb5287104dc5989eabc755f160c9a5c9a1cc783fe1e058b66",
        },
        "fc48252a-9dbb-4e07-bf9a-7af65a18f612": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "Z",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 1},
            "runHash": None,
        },
        "7bf0741f-bae4-410b-b662-fc34b47c27c9": {
            "key": "simcore/services/frontend/parameter/boolean",
            "version": "1.0.0",
            "label": "on",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": False},
            "runHash": None,
        },
        "09fd512e-0768-44ca-81fa-0cecab74ec1a": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval_2",
            "inputs": {
                "in_1": {
                    "nodeUuid": "13220a1d-a569-49de-b375-904301af9295",
                    "output": "output_2",
                }
            },
            "inputsUnits": {},
            "inputNodes": ["13220a1d-a569-49de-b375-904301af9295"],
            "parent": None,
            "thumbnail": "",
        },
        "76f607b4-8761-4f96-824d-cab670bc45f5": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval",
            "inputs": {
                "in_1": {
                    "nodeUuid": "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa",
                    "output": "output_2",
                }
            },
            "inputsUnits": {},
            "inputNodes": ["08d15a6c-ae7b-4ea1-938e-4ce81a360ffa"],
            "parent": None,
            "thumbnail": "",
        },
    }


@pytest.fixture
def workbench(workbench_db_column: dict[str, Any]) -> dict[NodeID, Node]:
    # convert to  model
    return parse_obj_as(dict[NodeID, Node], workbench_db_column)


@pytest.fixture
def fake_project(
    fake_project: ProjectDict, workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.mark.acceptance_test
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
