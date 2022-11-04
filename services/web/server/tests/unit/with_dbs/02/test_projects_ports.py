# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
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
from simcore_service_webserver.projects._ports import (
    get_project_inputs,
    get_project_outputs,
    set_project_inputs,
)


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
            "label": "x1",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 1},
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
        },
        "fc48252a-9dbb-4e07-bf9a-7af65a18f612": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "y",
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
            "label": "flag",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": True},
            "runHash": None,
        },
        "09fd512e-0768-44ca-81fa-0cecab74ec1a": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval",
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


def test_get_and_set_project_inputs(workbench: dict[NodeID, Node]):

    # get all inputs in the workbench
    project_inputs: dict[NodeID, Any] = get_project_inputs(workbench=workbench)

    assert project_inputs
    assert len(project_inputs) == 3

    # check input invariants
    for node_id in project_inputs:
        input_node = workbench[node_id]

        # has no inputs
        assert not input_node.inputs
        # has only one output called out_1
        assert input_node.outputs
        assert list(input_node.outputs.keys()) == ["out_1"]

    # update
    input_port_ids = list(project_inputs.keys())
    assert input_port_ids == 3
    input_0 = input_port_ids[0]
    input_1 = input_port_ids[1]
    input_2 = input_port_ids[2]

    set_project_inputs(
        workbench=workbench, update={input_0: 42, input_1: 3, input_2: False}
    )
    assert get_project_inputs(workbench=workbench) == {
        input_0: 42,
        input_1: 3,
        input_2: False,
    }


def test_get_project_outputs(workbench: dict[NodeID, Node]):

    # get all outputs in the workbench
    project_outputs: dict[NodeID, Any] = get_project_outputs(workbench=workbench)

    assert project_outputs
    assert len(project_outputs) == 2

    # check output node invariant
    for node_id in project_outputs:
        output_node = workbench[node_id]

        # has no outputs
        assert not output_node.outputs
        # has only one input called in_1
        assert output_node.inputs
        assert list(output_node.inputs.keys()) == ["in_1"]


@pytest.mark.skip(reason="UNDER DEV")
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPNotImplemented),
    ],
)
async def test_it1(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: dict[str, Any],
    mock_catalog_service_api_responses: None,
    expected: type[web.HTTPException],
):
    assert client.app
    project_workbench = user_project["workbench"]
    for node_id in project_workbench:
        url = client.app.router["replace_node_resources"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        response = await client.put(f"{url}", json={})
        await assert_status(response, expected)

    project_id = user_project["uuid"]
    node_id = list(project_workbench.keys())[0]

    # clone_project
    resp = await client.get(f"/v0/projects/{project_id}:clone")
    project_clone = (await resp.json())["data"]

    # get_project_ports
    # resp = await client.get(f"/v0/projects/{project_clone.uuid}/ports")
    # project_ports = (await resp.json())["data"]

    # ports is metadata => schemas
    # inputs/outputs are data

    # replace_project_inputs = set
    resp = await client.put(f"/v0/projects/{project_clone.uuid}/inputs")

    # update_project_inputs
    resp = await client.patch(f"/v0/projects/{project_clone.uuid}/inputs")

    # get_project_inputs (actual data)
    resp = await client.get(f"/v0/projects/{project_clone.uuid}/inputs")

    # get_project_outputs (actual data)
    resp = await client.get(f"/v0/projects/{project_clone.uuid}/outputs")

    # ---
    resp = await client.get(
        f"/v0/projects/{project_id}/nodes/{node_id}/ports/{port_key}"
    )
