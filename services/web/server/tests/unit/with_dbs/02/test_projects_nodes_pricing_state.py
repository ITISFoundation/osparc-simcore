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

import re
from typing import Any
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingPlanGet,
    RutPricingUnitGet,
)
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.project_nodes_pricing import (
    T3_MEDIUM_NAME,
    get_node_pricing_state,
    make_pricing_unit,
    regex_for_rut_pricing_unit,
    set_node_required_resources,
    single_container_required_resources,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.products._application_keys import PRODUCTS_APPKEY
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.resource_usage.settings import get_plugin_settings
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.epic("sanderegg/9851", flips_in="PR2")
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_writes_no_pricing_links(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    asyncpg_engine: AsyncEngine,
):
    """W5: creating a project (new, copy, template or api-server job) writes
    `projects_nodes` rows but NEVER a `projects_node_to_pricing_unit` link, and
    makes no resource-usage-tracker call (none is mocked here and aioresponses
    would raise on an unexpected HTTP call).

    ⚠️ The pricing/resources ownership rework (PR 2) intends to link the default
    pricing unit and size COMPUTATIONAL nodes at creation; when that lands,
    computational nodes here must be expected to have a default link and
    dask-sized resources (dynamic/frontend nodes keep having no link).
    """
    assert client.app

    state = await get_node_pricing_state(asyncpg_engine, user_project["uuid"])
    assert state, "the test project must have persisted nodes"

    for node_state in state.values():
        assert node_state.pricing_plan_id is None
        assert node_state.pricing_unit_id is None


#
# W2b: starting a dynamic service in a BILLED product, on a node with no pricing link.
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
def mock_rut_default_pricing_unit(client: TestClient, aioresponses_mocker: AioResponsesMock) -> RutPricingUnitGet:
    """RUT: the service's default plan/unit is unit 1 (t3.medium, non-zero cost)."""
    assert client.app
    settings = get_plugin_settings(client.app)
    default_unit = make_pricing_unit(
        pricing_unit_id=_DEFAULT_PRICING_UNIT_ID, default=True, aws_ec2_instance=T3_MEDIUM_NAME
    )
    default_plan = RutPricingPlanGet.model_validate(RutPricingPlanGet.model_json_schema()["examples"][0]).model_copy(
        update={"pricing_plan_id": _DEFAULT_PRICING_PLAN_ID, "pricing_units": [default_unit]}
    )
    aioresponses_mocker.get(
        re.compile(rf"^{re.escape(f'{settings.api_base_url}')}/services/[^/]+/[^/]+/pricing-plan.*$"),
        payload=jsonable_encoder(default_plan),
        repeat=True,
    )
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _DEFAULT_PRICING_PLAN_ID, _DEFAULT_PRICING_UNIT_ID),
        payload=jsonable_encoder(default_unit),
        repeat=True,
    )
    return default_unit


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


@pytest.mark.epic("sanderegg/T2", flips_in="PR2")
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
    pricing link, lazily links the DEFAULT plan/unit of the service and resizes
    `required_resources` with the DYNAMIC-SIDECAR formula of that unit's machine
    (the sizing is computed by director-v2).

    ⚠️ The pricing/resources ownership rework (PR 2) moves link/size creation to
    project creation and node addition, keeping the start only as a repair: the END
    state asserted here is intended to stay, but the RUT/sizing calls below may
    disappear once the link is already in place.
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
