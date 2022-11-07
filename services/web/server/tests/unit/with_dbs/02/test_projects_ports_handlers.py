# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from copy import deepcopy
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.projects_nodes import Node, NodeID
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from settings_library.catalog import CatalogSettings
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.catalog_settings import get_plugin_settings
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects import projects_ports_handlers
from simcore_service_webserver.projects.project_models import ProjectDict
from yarl import URL


@pytest.mark.parametrize(
    "route",
    projects_ports_handlers.routes,
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
def mock_catalog_service_api_responses(client, aioresponses_mocker):
    settings: CatalogSettings = get_plugin_settings(client.app)
    url_pattern = re.compile(f"^{settings.base_url}+/.*$")

    aioresponses_mocker.get(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.post(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.put(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.patch(
        url_pattern,
        payload={"data": {}},
        repeat=True,
    )
    aioresponses_mocker.delete(
        url_pattern,
        repeat=True,
    )


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
def user_project(
    user_project: dict[str, Any], workbench_db_column: dict[str, Any]
) -> ProjectDict:
    # OVERRIDES user_project
    project = deepcopy(user_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.mark.skip(reason="UNDER DEV")
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPUnauthorized),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_user_story(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mock_catalog_service_api_responses: None,
    expected: type[web.HTTPException],
):
    assert client.app

    project_id = user_project["uuid"]

    # NOTE: next PR we will implement this part
    # resp = await client.get(f"/v0/projects/{project_id}:clone")
    # project_clone, _ = await assert_status(resp, expected_cls=expected)

    # Now, on the cloned project
    # project_id = project_clone["uuid"]

    # get_project_inputs
    expected_url = client.app.router["get_project_inputs"].url_for(
        project_id=project_id
    )
    assert URL(f"/v0/projects/{project_id}/inputs") == expected_url

    resp = await client.get(f"/v0/projects/{project_id}/inputs")
    project_inputs, _ = await assert_status(resp, expected_cls=expected)

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
        json=[{"key": "38a0d401-af4b-4ea7-ab4c-5005c712a5469", "value": 42}],
    )
    project_inputs, _ = await assert_status(resp, expected_cls=expected)

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
    project_outputs, _ = await assert_status(resp, expected_cls=expected)

    assert project_outputs == {
        "data": {
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
    }
