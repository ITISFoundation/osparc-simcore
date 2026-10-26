# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


import re
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingUnitGet,
)
from models_library.projects_nodes_io import NodeID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.project_nodes_pricing import (
    R5_4XLARGE_NAME,
    T3_MEDIUM_NAME,
    get_node_pricing_state,
    make_pricing_unit,
    regex_for_rut_pricing_unit,
    set_node_required_resources,
    single_container_required_resources,
)
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.aiohttp import status
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.resource_usage.settings import get_plugin_settings
from sqlalchemy.ext.asyncio import AsyncEngine

API_PREFIX = "/" + api_version_prefix


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_project_node_pricing_unit_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    assert resp.status == status.HTTP_401_UNAUTHORIZED if user_role == UserRole.ANONYMOUS else status.HTTP_200_OK


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_node_pricing_unit_user_project_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    node_id = next(iter(user_project["workbench"]))
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data is None

    # Now we will log as a different user who doesnt have access to the project
    async with LoggedUser(client):
        base_url = client.app.router["get_project_node_pricing_unit"].url_for(
            project_id=user_project["uuid"], node_id=node_id
        )
        resp = await client.get(f"{base_url}")
        _, errors = await assert_status(resp, status.HTTP_403_FORBIDDEN)
        assert errors


_PRICING_PLAN_ID = 1
_PRICING_UNIT_ID_1 = 1
_PRICING_UNIT_ID_2 = 2


@pytest.fixture
def mock_rut_api_responses(client: TestClient, aioresponses_mocker: AioResponsesMock) -> AioResponsesMock:
    assert client.app
    settings: ResourceUsageTrackerSettings = get_plugin_settings(client.app)

    pricing_unit_example: dict[str, Any] = RutPricingUnitGet.model_json_schema()["examples"][0]
    pricing_unit_get_base = RutPricingUnitGet.model_validate(pricing_unit_example)
    pricing_unit_get_1 = pricing_unit_get_base.model_copy()
    pricing_unit_get_1.pricing_unit_id = _PRICING_UNIT_ID_1
    pricing_unit_get_2 = pricing_unit_get_base.model_copy()
    pricing_unit_get_2.pricing_unit_id = _PRICING_UNIT_ID_2

    aioresponses_mocker.get(
        re.compile(f"^{settings.api_base_url}/pricing-plans/1/pricing-units/1+.+$"),
        payload=jsonable_encoder(pricing_unit_get_1),
        repeat=True,
    )
    aioresponses_mocker.get(
        re.compile(f"^{settings.api_base_url}/pricing-plans/1/pricing-units/2+.+$"),
        payload=jsonable_encoder(pricing_unit_get_2),
        repeat=True,
    )

    return aioresponses_mocker


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_project_wallets_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_rut_api_responses: AioResponsesMock,
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    # a comp node: frontend nodes are never sized (see frontend test below)
    node_id = _get_node_id_for_service_class(user_project, "comp")
    assert client.app
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data is None

    # Now we will connect pricing unit to the project node
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=user_project["uuid"],
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_1}",
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
    mocked_director_v2_node_sizing.assert_called_once()
    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data["pricingUnitId"] == _PRICING_UNIT_ID_1

    # Now we will connect different pricing unit
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=user_project["uuid"],
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_2}",
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    base_url = client.app.router["get_project_node_pricing_unit"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(f"{base_url}")
    data, _ = await assert_status(resp, expected)
    assert data["pricingUnitId"] == _PRICING_UNIT_ID_2


#
# CHARACTERIZATION TESTS (pin the state of the DB, not the code that produces it).
#
# These assert what `PUT .../pricing-plan/{plan}/pricing-unit/{unit}` persists in
# `projects_node_to_pricing_unit` and `projects_nodes.required_resources`.
# All expected CPU/RAM numbers are hand-computed literals from the fixed EC2
# specs in `pytest_simcore.helpers.project_nodes_pricing`:
#   r5.4xlarge = 16 CPU / 128 GiB
#   computational node, dask-worker formula:
#     cpu = 16 - 0.1 = 15.9,  ram = int(137438953472 * 0.9) = 123695058124
#   dynamic node, dynamic-sidecar formula:
#     cpu = max(0.5, 16 - 1.4) = 14.6
#     ram = int(137438953472 - 0.1*137438953472 - 1 GiB) = 122621316300
# The sizing itself is computed by director-v2 (RPC `compute_node_resources_for_hardware`),
# pinned by its own tests; here director-v2 is replaced by the fixed test double
# `mocked_director_v2_node_sizing`.
#


@pytest.fixture
def mock_rut_fixed_pricing_units(
    client: TestClient, aioresponses_mocker: AioResponsesMock
) -> dict[int, RutPricingUnitGet]:
    """Two pricing units with FIXED hardware: unit 1 -> t3.medium (default),
    unit 2 -> r5.4xlarge (non-default)."""
    assert client.app
    settings: ResourceUsageTrackerSettings = get_plugin_settings(client.app)
    units = {
        _PRICING_UNIT_ID_1: make_pricing_unit(
            pricing_unit_id=_PRICING_UNIT_ID_1, default=True, aws_ec2_instance=T3_MEDIUM_NAME
        ),
        _PRICING_UNIT_ID_2: make_pricing_unit(
            pricing_unit_id=_PRICING_UNIT_ID_2, default=False, aws_ec2_instance=R5_4XLARGE_NAME
        ),
    }
    for pricing_unit_id, unit in units.items():
        aioresponses_mocker.get(
            regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, pricing_unit_id),
            payload=jsonable_encoder(unit),
            repeat=True,
        )
    return units


def _get_node_id_for_service_class(user_project: ProjectDict, service_class: str) -> str:
    for node_id, node in user_project["workbench"].items():
        # service keys look like simcore/services/{comp|dynamic|frontend}/...
        if node["key"].count("/") >= 3 and f"/{service_class}/" in node["key"]:
            return node_id
    # pytest.fail raises, so this never returns
    return pytest.fail(f"no /{service_class}/ node in the test project")


@pytest.mark.parametrize(
    "user_role,service_class,expected_cpu,expected_ram",
    [
        (UserRole.USER, "comp", 15.9, 123695058124),
        (UserRole.USER, "dynamic", 14.6, 122621316300),
    ],
    ids=["computational", "dynamic"],
)
async def test_connect_pricing_unit_persists_link_and_sizes_node(
    service_class: str,
    expected_cpu: float,
    expected_ram: int,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    asyncpg_engine: AsyncEngine,
    mock_rut_fixed_pricing_units: dict[int, RutPricingUnitGet],
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    """W3 (comp) / W4 (dynamic): connecting a pricing unit creates the link and
    resizes `required_resources` for the unit's EC2 machine.

    The sizing formula is picked by director-v2 according to the node class:
    computational nodes get the DASK-WORKER formula, dynamic nodes the
    DYNAMIC-SIDECAR one (see the hand-computed values in the section header).
    """
    assert client.app
    node_id = _get_node_id_for_service_class(user_project, service_class)
    project_id = user_project["uuid"]

    # make the sizing deterministic: a single-container resource spec on the node
    await set_node_required_resources(
        asyncpg_engine,
        project_id,
        node_id,
        single_container_required_resources(user_project["workbench"][node_id]["key"]),
    )

    # no link yet
    state = await get_node_pricing_state(asyncpg_engine, project_id)
    assert state[NodeID(node_id)].pricing_unit_id is None

    # ACT: connect the NON-default pricing unit (r5.4xlarge: 16 CPU / 128 GiB)
    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=project_id,
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_2}",
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # ASSERT: DB state
    state = await get_node_pricing_state(asyncpg_engine, project_id)
    node_state = state[NodeID(node_id)]
    assert node_state.pricing_plan_id == _PRICING_PLAN_ID
    assert node_state.pricing_unit_id == _PRICING_UNIT_ID_2

    assert node_state.required_resources
    resources = node_state.required_resources["container"]["resources"]
    assert resources["CPU"]["limit"] == pytest.approx(expected_cpu)
    assert resources["CPU"]["reservation"] == pytest.approx(expected_cpu)
    assert resources["RAM"]["limit"] == expected_ram
    assert resources["RAM"]["reservation"] == expected_ram


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_connect_pricing_unit_to_frontend_node_does_not_size_it(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    asyncpg_engine: AsyncEngine,
    mock_rut_fixed_pricing_units: dict[int, RutPricingUnitGet],
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    """A frontend node is owned by the frontend and never runs on a machine: the
    web-server must not even ask director-v2 to size it.
    """
    assert client.app
    node_id = _get_node_id_for_service_class(user_project, "frontend")
    project_id = user_project["uuid"]

    initial_resources = single_container_required_resources(user_project["workbench"][node_id]["key"])
    await set_node_required_resources(asyncpg_engine, project_id, node_id, initial_resources)

    base_url = client.app.router["connect_pricing_unit_to_project_node"].url_for(
        project_id=project_id,
        node_id=node_id,
        pricing_plan_id=f"{_PRICING_PLAN_ID}",
        pricing_unit_id=f"{_PRICING_UNIT_ID_2}",
    )
    resp = await client.put(f"{base_url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    mocked_director_v2_node_sizing.assert_not_called()

    state = await get_node_pricing_state(asyncpg_engine, project_id)
    node_state = state[NodeID(node_id)]
    assert node_state.pricing_unit_id == _PRICING_UNIT_ID_2
    assert node_state.required_resources == initial_resources
