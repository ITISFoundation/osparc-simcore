# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""CHARACTERIZATION TESTS pinning the pricing/resources state of the database
(see `pytest_simcore.helpers.project_nodes_pricing`):

- `projects_nodes.required_resources`
- `projects_node_to_pricing_unit`

These tests describe the STATE produced by project creation, not the code that
produces it, so they keep passing while the responsibility for writing that state
moves from director-v2 to the web-server (pricing/resources ownership rework).
Tests marked `@pytest.mark.epic(...)` assert TODAY's behaviour and name, in their
docstring, the PR of the epic intended to change them (`flips_in`).

The dynamic-node "linked + sized with the dynamic formula at dynamic start" (W2b,
below) and the computational-node "linked to the default unit + sized on the first
pipeline update" behaviors (D1-D6) are exercised from the director-v2 side in
`services/director-v2/tests/unit/with_dbs`.
"""

from typing import Any
from unittest import mock
from urllib.parse import urlparse

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingUnitGet,
)
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import ServiceResourcesDict
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.project_nodes_pricing import (
    get_node_pricing_state,
    set_node_required_resources,
    single_container_required_resources,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.long_running_tasks.models import TaskStatus
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.products._application_keys import PRODUCTS_APPKEY
from simcore_service_webserver.projects.models import ProjectDict
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

# Hand-computed expectation (t3.medium = 2 CPU / 4 GiB, dask-worker formula):
#   cpu = max(0.1, 2.0 - 0.1) = 1.9
#   ram = int(4294967296 * 0.9) = 3865470566
#

_FILE_PICKER_NODE_ID = "106bfd6b-4b94-4e9e-9cd4-2f8e446f9a9e"
_COMP_NODE_ID = "0e5cc0cf-0b75-4b17-b995-899cb95a5eeb"
_DYNAMIC_NODE_ID = "b18cc951-4e0a-4f1f-9f2d-98b1d1ba72a1"

_WORKBENCH: dict[str, Any] = {
    _FILE_PICKER_NODE_ID: {
        "key": "simcore/services/frontend/file-picker",
        "version": "1.0.0",
        "label": "File Picker",
        "inputs": {},
        "outputs": {},
    },
    _COMP_NODE_ID: {
        "key": "simcore/services/comp/itis/sleeper",
        "version": "2.1.7",
        "label": "sleeper",
        "inputs": {},
        "outputs": {},
    },
    _DYNAMIC_NODE_ID: {
        "key": "simcore/services/dynamic/pytest-dynamic-service",
        "version": "0.0.0",
        "label": "dyn",
        "inputs": {},
        "outputs": {},
    },
}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_links_default_unit_and_sizes_computational_nodes(
    client: TestClient,
    logged_user: UserInfoDict,
    asyncpg_engine: AsyncEngine,
    project_db_cleaner: None,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    """W5: creating a new project (POST /v0/projects) links the DEFAULT pricing
    unit and sizes every COMPUTATIONAL node right away, while dynamic and frontend
    nodes get NO link at creation (copy/template cloning is characterized in
    test_projects_service__copy.py; api-server jobs use this same creation path).
    """
    assert client.app

    create_url = client.app.router["create_project"].url_for()
    resp = await client.post(
        f"{create_url}",
        json={
            "name": "w5-project",
            "description": "pricing state at creation",
            "workbench": _WORKBENCH,
            "accessRights": {},
        },
    )
    data, _ = await assert_status(resp, status.HTTP_202_ACCEPTED)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            rsp = await client.get(urlparse(data["status_href"]).path)
            status_data, _ = await assert_status(rsp, status.HTTP_200_OK)
            task_status = TaskStatus.model_validate(status_data)
            assert task_status.done, f"creation task not done: {task_status}"

    rsp = await client.get(urlparse(data["result_href"]).path)
    new_project, _ = await assert_status(rsp, status.HTTP_201_CREATED)

    # only the computational node is sized at creation: exactly one RPC call
    mocked_director_v2_node_sizing.assert_called_once()

    state = await get_node_pricing_state(asyncpg_engine, new_project["uuid"])
    assert len(state) == len(_WORKBENCH)

    # computational node: linked to the default plan/unit and dask-sized
    comp_state = state[NodeID(_COMP_NODE_ID)]
    assert comp_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert comp_state.pricing_unit_id == mock_rut_default_pricing_unit.pricing_unit_id
    assert comp_state.required_resources
    comp_resources = comp_state.required_resources["container"]["resources"]
    assert comp_resources["CPU"]["limit"] == pytest.approx(1.9)
    assert comp_resources["RAM"]["limit"] == 3865470566
    assert comp_resources["RAM"]["reservation"] == 3865470566

    # dynamic and frontend nodes: NOT linked, catalog resources untouched
    for node_id in (_DYNAMIC_NODE_ID, _FILE_PICKER_NODE_ID):
        node_state = state[NodeID(node_id)]
        assert node_state.pricing_plan_id is None
        assert node_state.pricing_unit_id is None
        assert node_state.required_resources == jsonable_encoder(mock_service_resources)


#
# W2b: starting a dynamic service in a BILLED product, on a node with no pricing link
# (dynamic nodes are never linked at creation, so this path always fires for them).
#
# Hand-computed expectation (t3.medium = 2 CPU / 4 GiB, dynamic-sidecar formula):
#   cpu = max(0.5, 2.0 - 1.4) = 0.6
#   ram = int(4294967296 - 0.1*4294967296 - 1 GiB) = 2791728742
#

_DEFAULT_PRICING_PLAN_ID = 1
_DEFAULT_PRICING_UNIT_ID = 1  # the default one, on t3.medium
_PROJECT_WALLET_ID = WalletID(7)


@pytest.fixture
def app_environment(app_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    # the wallet/pricing/hardware block of the dynamic start is gated on this flag
    monkeypatch.setenv("WEBSERVER_CREDIT_COMPUTATION_ENABLED", "1")
    return app_environment | {"WEBSERVER_CREDIT_COMPUTATION_ENABLED": "1"}


@pytest.fixture
def billed_product(client: TestClient, osparc_product_name: ProductName) -> None:
    """Marks the request's product as payment-enabled (products are read per request
    from the app-cached dictionary)."""
    assert client.app
    products = client.app[PRODUCTS_APPKEY]
    products[osparc_product_name] = products[osparc_product_name].model_copy(update={"is_payment_enabled": True})


@pytest.fixture
def mock_project_wallet_with_credits(mocker: MockerFixture) -> None:
    """The project is connected to a wallet that has credits."""
    # NOTE: autospec of a coroutine function gives an AsyncMock
    mocker.patch(
        "simcore_service_webserver.projects._projects_service._wallets_service.get_project_wallet",
        autospec=True,
        return_value=mock.Mock(wallet_id=_PROJECT_WALLET_ID),
    )
    wallet_example: dict[str, Any] = WalletGetWithAvailableCredits.model_json_schema()["examples"][0]
    wallet = WalletGetWithAvailableCredits.model_validate({**wallet_example, "wallet_id": int(_PROJECT_WALLET_ID)})
    assert wallet.available_credits > 0
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.get_wallet_with_available_credits_by_user_and_wallet",
        autospec=True,
        return_value=wallet,
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_start_dynamic_service_links_default_unit_and_sizes_with_dynamic_formula(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    asyncpg_engine: AsyncEngine,
    billed_product: None,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mock_project_wallet_with_credits: None,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
):
    """W2b: starting a dynamic service in a billed product, on a node without any
    pricing link, links the DEFAULT plan/unit of the service and resizes
    `required_resources` with the DYNAMIC-SIDECAR formula of that unit's machine
    (the sizing is computed by director-v2). Dynamic nodes are never linked at
    creation, so this path stays the (only) writer of a dynamic node's link.
    """
    assert client.app

    dynamic_node_id = next(node_id for node_id, node in user_project["workbench"].items() if "/dynamic/" in node["key"])
    project_id = user_project["uuid"]

    # deterministic starting point: single-container resources, no link
    await set_node_required_resources(
        asyncpg_engine,
        project_id,
        dynamic_node_id,
        single_container_required_resources(user_project["workbench"][dynamic_node_id]["key"]),
    )
    state_before = await get_node_pricing_state(asyncpg_engine, project_id)
    assert state_before[NodeID(dynamic_node_id)].pricing_plan_id is None
    assert state_before[NodeID(dynamic_node_id)].pricing_unit_id is None

    url = client.app.router["start_node"].url_for(project_id=project_id, node_id=dynamic_node_id)
    rsp = await client.post(f"{url}")
    assert rsp.status == status.HTTP_204_NO_CONTENT, await rsp.text()

    mocked_dynamic_services_interface["dynamic_scheduler.api.run_dynamic_service"].assert_called_once()
    mocked_director_v2_node_sizing.assert_called_once()

    state_after = await get_node_pricing_state(asyncpg_engine, project_id)
    node_state = state_after[NodeID(dynamic_node_id)]
    assert node_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert node_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID

    assert node_state.required_resources
    resources = node_state.required_resources["container"]["resources"]
    assert resources["CPU"]["limit"] == pytest.approx(0.6)
    assert resources["RAM"]["limit"] == 2791728742
    assert resources["RAM"]["reservation"] == 2791728742

    # starting one dynamic service leaves every other node untouched
    for node_id, other_state in state_after.items():
        if node_id != NodeID(dynamic_node_id):
            assert other_state == state_before[node_id]
