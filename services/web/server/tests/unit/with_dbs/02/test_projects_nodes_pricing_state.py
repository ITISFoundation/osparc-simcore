# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
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

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Final
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from annotated_types import doc  # pyright: ignore[reportAttributeAccessIssue]
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingUnitGet,
)
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.project_nodes_pricing import (
    fake_compute_node_resources_for_hardware,
    get_node_pricing_state,
    regex_for_rut_pricing_unit,
    resources_limits,
    set_node_pricing_link,
    set_node_required_resources,
    single_container_required_resources,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import _projects_service
from simcore_service_webserver.projects._projects_repository_legacy import ProjectDBAPI
from simcore_service_webserver.projects.api import repair_projects_nodes_pricing_and_resources
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.resource_usage.settings import (
    get_plugin_settings as get_rut_plugin_settings,
)
from sqlalchemy.ext.asyncio import AsyncEngine

_FILE_PICKER_NODE_ID: Final[str] = "106bfd6b-4b94-4e9e-9cd4-2f8e446f9a9e"
_COMP_NODE_ID: Final[str] = "0e5cc0cf-0b75-4b17-b995-899cb95a5eeb"
_DYNAMIC_NODE_ID: Final[str] = "b18cc951-4e0a-4f1f-9f2d-98b1d1ba72a1"

_WORKBENCH: Final[dict[str, Any]] = {
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

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
]


@pytest.fixture
def create_project(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    request_create_project: Callable[..., Awaitable[ProjectDict]],
) -> Callable[[str, dict[str, Any]], Awaitable[ProjectDict]]:
    """Creates a project through the endpoint and waits for the long-running task"""

    async def _create(name: str, workbench: dict[str, Any]) -> ProjectDict:
        return await request_create_project(
            client,
            status.HTTP_202_ACCEPTED,
            status.HTTP_201_CREATED,
            logged_user,
            primary_group,
            project={"name": name, "workbench": workbench},
        )

    return _create


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_in_a_non_billed_product_leaves_the_resources_to_the_user(
    *,
    client: TestClient,
    create_project: Callable[[str, dict[str, Any]], Awaitable[ProjectDict]],
    logged_user: UserInfoDict,
    sqlalchemy_async_engine: AsyncEngine,
    project_db_cleaner: None,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    with_permitted_override_services_specifications: None,
):
    """Creating a project in a product that does not pay for computational resources
    links nothing and sizes nothing, which is what keeps
    `PUT .../nodes/{node_id}/resources` usable: it answers 409 on a node that has a
    pricing link (see `test_replace_node_resources_raises_409_if_pricing_unit_is_connected`).
    """
    assert client.app
    new_project = await create_project("non-billed-project", _WORKBENCH)

    # nothing is sized, nothing is linked, and every node keeps the catalog's resources
    mocked_director_v2_node_sizing.assert_not_called()
    state = await get_node_pricing_state(sqlalchemy_async_engine, new_project["uuid"])
    assert len(state) == len(_WORKBENCH)
    for node_id, node_state in state.items():
        assert node_state.pricing_plan_id is None, f"{node_id} got linked in a non-billed product"
        assert node_state.pricing_unit_id is None
        assert node_state.required_resources == jsonable_encoder(mock_service_resources)

    # and the user can still write them. The payload keeps the containers the node has
    # (the catalog mock answers the same resources for every service) and changes one limit
    payload = jsonable_encoder(mock_service_resources)
    for container_specs in payload.values():
        container_specs["resources"]["CPU"]["limit"] = 3
    url = client.app.router["replace_node_resources"].url_for(project_id=new_project["uuid"], node_id=_COMP_NODE_ID)
    resp = await client.put(f"{url}", json=payload)
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["container"]["resources"]["CPU"]["limit"] == 3


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_links_default_unit_and_sizes_only_comp_nodes(
    *,
    client: TestClient,
    create_project: Callable[[str, dict[str, Any]], Awaitable[ProjectDict]],
    logged_user: UserInfoDict,
    sqlalchemy_async_engine: AsyncEngine,
    project_db_cleaner: None,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    with_billed_product: None,
):
    """Creating a new project (POST /v0/projects) in a billed product links the default
    pricing unit and sizes every node with a `simcore/services/comp` key, at creation.
    Dynamic and frontend nodes get no link there: a dynamic node is linked when it starts
    (below), a frontend node never. Copy and template cloning is characterized in
    test_projects_service__copy.py; api-server jobs use this same creation path.
    """
    assert client.app

    new_project = await create_project("billed-project", _WORKBENCH)

    # only the comp node is sized at creation: exactly one RPC call
    mocked_director_v2_node_sizing.assert_called_once()

    state = await get_node_pricing_state(sqlalchemy_async_engine, new_project["uuid"])
    assert len(state) == len(_WORKBENCH)

    # comp node: linked to the default plan/unit and sized with the dask-worker formula
    comp_state = state[NodeID(_COMP_NODE_ID)]
    assert comp_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert comp_state.pricing_unit_id == mock_rut_default_pricing_unit.pricing_unit_id
    assert comp_state.required_resources
    # hand-computed from t3.medium (2 CPU / 4 GiB) with the dask-worker formula:
    # cpu = max(0.1, 2.0 - 0.1) = 1.9, ram = int(4294967296 * 0.9) = 3865470566
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
# starting a dynamic service in a billed product, on a node with no pricing link
# (dynamic nodes are never linked at creation, so this path always fires for them)
#
# Hand-computed expectation (t3.medium = 2 CPU / 4 GiB, dynamic-sidecar formula):
#   cpu = max(0.5, 2.0 - 1.4) = 0.6
#   ram = int(4294967296 - 0.1*4294967296 - 1 GiB) = 2791728742
#

_DEFAULT_PRICING_PLAN_ID: Final[int] = 1
_DEFAULT_PRICING_UNIT_ID: Final[Annotated[int, doc("the product default, on t3.medium")]] = 1
_PROJECT_WALLET_ID: Final[WalletID] = WalletID(7)


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
    sqlalchemy_async_engine: AsyncEngine,
    with_billed_product: None,
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
        sqlalchemy_async_engine,
        project_id,
        dynamic_node_id,
        single_container_required_resources(user_project["workbench"][dynamic_node_id]["key"]),
    )
    state_before = await get_node_pricing_state(sqlalchemy_async_engine, project_id)
    assert state_before[NodeID(dynamic_node_id)].pricing_plan_id is None
    assert state_before[NodeID(dynamic_node_id)].pricing_unit_id is None

    url = client.app.router["start_node"].url_for(project_id=project_id, node_id=dynamic_node_id)
    rsp = await client.post(f"{url}")
    assert rsp.status == status.HTTP_204_NO_CONTENT, await rsp.text()

    mocked_dynamic_services_interface["dynamic_scheduler.api.run_dynamic_service"].assert_called_once()
    mocked_director_v2_node_sizing.assert_called_once()

    state_after = await get_node_pricing_state(sqlalchemy_async_engine, project_id)
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


#
# The repair that a billed start runs (see test_director_v2_handlers.py): links the
# nodes that have no usable link and sizes them. It runs on EVERY start, so it must be
# cheap for the nodes it already brought up to date, must never lose a node when
# director-v2 or the resource-usage tracker (RUT) is unreachable, and must not keep a node
# stuck on a link that is unusable in this product.
#

_UNKNOWN_PRICING_PLAN_ID: Final[Annotated[int, doc("a plan the product does not know")]] = 66
_UNKNOWN_PRICING_UNIT_ID: Final[Annotated[int, doc("a unit of the known plan that does not exist")]] = 77


def _comp_node_id(user_project: ProjectDict) -> NodeID:
    return NodeID(next(node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"]))


async def _repair(client: TestClient, logged_user: UserInfoDict, project_id: str, product_name: str) -> None:
    await repair_projects_nodes_pricing_and_resources(
        client.app,
        user_id=UserID(logged_user["id"]),
        project_ids=[ProjectID(project_id)],
        product_name=product_name,
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_repair_replaces_a_link_that_is_unknown_in_the_product(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    """A node linked to a plan/unit that RUT does not know in this
    product (e.g. a link copied from another product's template while RUT was
    unreachable) is re-linked to the DEFAULT unit and sized for its machine, instead of
    staying unusable for every future run.
    """
    assert client.app
    project_id = user_project["uuid"]
    node_id = _comp_node_id(user_project)

    await set_node_required_resources(
        sqlalchemy_async_engine,
        project_id,
        node_id,
        single_container_required_resources(user_project["workbench"][f"{node_id}"]["key"], cpu=0.1),
    )
    await set_node_pricing_link(
        sqlalchemy_async_engine,
        project_id,
        node_id,
        pricing_plan_id=_UNKNOWN_PRICING_PLAN_ID,
        pricing_unit_id=_UNKNOWN_PRICING_UNIT_ID,
    )
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(
            f"{get_rut_plugin_settings(client.app).api_base_url}",
            _UNKNOWN_PRICING_PLAN_ID,
            _UNKNOWN_PRICING_UNIT_ID,
        ),
        status=status.HTTP_404_NOT_FOUND,
        repeat=True,
    )

    await _repair(client, logged_user, project_id, osparc_product_name)

    state = await get_node_pricing_state(sqlalchemy_async_engine, project_id)
    node_state = state[node_id]
    assert node_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert node_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    assert node_state.required_resources
    resources = node_state.required_resources["container"]["resources"]
    assert resources["CPU"]["limit"] == pytest.approx(1.9)
    assert resources["RAM"]["limit"] == 3865470566


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_repair_writes_nothing_for_a_node_already_sized(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    mocker: MockerFixture,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    """Every billed start repairs every node, so a node that is already sized for the
    machine of its linked unit must not be written again: only the not-yet-sized dynamic
    node of the test project gets a write here.
    """
    assert client.app
    project_id = user_project["uuid"]
    node_id = _comp_node_id(user_project)
    dynamic_node_id = NodeID(
        next(node_id_ for node_id_, node in user_project["workbench"].items() if "/dynamic/" in node["key"])
    )

    # the node is linked to the default unit and its resources ARE the sizing result of
    # that unit's machine (t3.medium, dask-worker formula: 1.9 CPU / 3865470566 B)
    await set_node_pricing_link(
        sqlalchemy_async_engine,
        project_id,
        node_id,
        pricing_plan_id=_DEFAULT_PRICING_PLAN_ID,
        pricing_unit_id=_DEFAULT_PRICING_UNIT_ID,
    )
    await set_node_required_resources(
        sqlalchemy_async_engine,
        project_id,
        node_id,
        single_container_required_resources(
            user_project["workbench"][f"{node_id}"]["key"], cpu=1.9, ram_bytes=3865470566
        ),
    )
    # the dynamic node still needs its default link and sizing, so the repair below has
    # exactly one node left to write
    await set_node_required_resources(
        sqlalchemy_async_engine,
        project_id,
        dynamic_node_id,
        single_container_required_resources(user_project["workbench"][f"{dynamic_node_id}"]["key"]),
    )
    update_node = mocker.spy(ProjectDBAPI.get_from_app_context(client.app), "update_project_node")

    await _repair(client, logged_user, project_id, osparc_product_name)

    # the sizing was computed (the web-server cannot know the result without asking) and
    # written once, for the dynamic node only
    assert mocked_director_v2_node_sizing.called
    assert update_node.call_count == 1
    written_node_ids = {call.args[2] for call in update_node.call_args_list}
    assert written_node_ids == {dynamic_node_id}

    state = await get_node_pricing_state(sqlalchemy_async_engine, project_id)
    sized_resources = state[node_id].required_resources
    assert sized_resources
    assert sized_resources["container"]["resources"]["CPU"]["limit"] == pytest.approx(1.9)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_repair_keeps_link_and_resources_when_sizing_fails_and_completes_later(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
):
    """director-v2 unreachable: the repair still links the DEFAULT unit (the link is
    written before the sizing) and leaves `required_resources` untouched, and the next
    repair completes the sizing.
    """
    assert client.app
    project_id = user_project["uuid"]
    node_id = _comp_node_id(user_project)
    seed = single_container_required_resources(
        user_project["workbench"][f"{node_id}"]["key"], cpu=0.1, ram_bytes=1024**3
    )
    await set_node_required_resources(sqlalchemy_async_engine, project_id, node_id, seed)

    # clusters-keeper unreachable -> ClustersKeeperNotAvailableError, swallowed here
    mocked_director_v2_node_sizing.side_effect = TimeoutError("clusters-keeper unreachable")
    await _repair(client, logged_user, project_id, osparc_product_name)

    state = await get_node_pricing_state(sqlalchemy_async_engine, project_id)
    node_state = state[node_id]
    assert node_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert node_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    assert node_state.required_resources == jsonable_encoder(seed)

    mocked_director_v2_node_sizing.side_effect = fake_compute_node_resources_for_hardware
    await _repair(client, logged_user, project_id, osparc_product_name)

    state = await get_node_pricing_state(sqlalchemy_async_engine, project_id)
    required_resources = state[node_id].required_resources
    assert required_resources
    resources = required_resources["container"]["resources"]
    assert resources["CPU"]["limit"] == pytest.approx(1.9)
    assert resources["RAM"]["limit"] == 3865470566


_SECOND_COMP_NODE_ID: Final[str] = "5b2af27d-b4a4-4a4b-9c9c-42ce9dd3a5f1"

_TWO_COMP_NODES_WORKBENCH: Final[
    Annotated[dict[str, Any], doc("same service as _COMP_NODE_ID: a project's nodes typically share one")]
] = _WORKBENCH | {
    _SECOND_COMP_NODE_ID: {
        "key": _WORKBENCH[_COMP_NODE_ID]["key"],
        "version": _WORKBENCH[_COMP_NODE_ID]["version"],
        "label": "sleeper_2",
        "inputs": {},
        "outputs": {},
    }
}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_asks_rut_once_per_service(
    *,
    client: TestClient,
    create_project: Callable[[str, dict[str, Any]], Awaitable[ProjectDict]],
    logged_user: UserInfoDict,
    sqlalchemy_async_engine: AsyncEngine,
    project_db_cleaner: None,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    with_billed_product: None,
    mocker: MockerFixture,
):
    """Two nodes of the same service share the answer about its DEFAULT pricing unit:
    creation asks the resource-usage tracker (RUT) once per distinct service, not per node,
    and still sizes every node.
    """
    assert client.app
    default_plan_lookup = mocker.spy(_projects_service.rut_api, "get_default_service_pricing_plan")

    new_project = await create_project("dedupe-project", _TWO_COMP_NODES_WORKBENCH)

    assert default_plan_lookup.call_count == 1
    # sizing is per node: both computational nodes get their own request
    assert mocked_director_v2_node_sizing.call_count == 2

    state = await get_node_pricing_state(sqlalchemy_async_engine, new_project["uuid"])
    for node_id in (_COMP_NODE_ID, _SECOND_COMP_NODE_ID):
        node_state = state[NodeID(node_id)]
        assert node_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
        assert node_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
        assert node_state.required_resources
        assert node_state.required_resources["container"]["resources"] == resources_limits(
            cpu=1.9, ram_bytes=3865470566
        )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_node_creation_links_default_unit_and_sizes_it(
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    with_billed_product: None,
):
    """Adding a computational node to a project of a BILLED product links the DEFAULT
    unit and sizes it right away. An unreachable director-v2 leaves the link in place and
    the catalog resources untouched, and does not fail the request: the next billed start
    completes the sizing (see the repair tests above).
    """
    assert client.app
    create_url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {"service_key": _WORKBENCH[_COMP_NODE_ID]["key"], "service_version": "2.1.7", "service_id": None}

    resp = await client.post(f"{create_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    node_id = NodeID(data["node_id"])

    mocked_director_v2_node_sizing.assert_called_once()
    state = await get_node_pricing_state(sqlalchemy_async_engine, user_project["uuid"])
    node_state = state[node_id]
    assert node_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert node_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    assert node_state.required_resources
    assert node_state.required_resources["container"]["resources"] == resources_limits(cpu=1.9, ram_bytes=3865470566)

    # now with director-v2 unreachable
    mocked_director_v2_node_sizing.side_effect = TimeoutError("director-v2 unreachable")
    mocked_director_v2_node_sizing.reset_mock()
    resp = await client.post(f"{create_url}", json=body)
    data, _ = await assert_status(resp, status.HTTP_201_CREATED)
    unsized_node_id = NodeID(data["node_id"])

    state = await get_node_pricing_state(sqlalchemy_async_engine, user_project["uuid"])
    unsized_state = state[unsized_node_id]
    assert unsized_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert unsized_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    assert unsized_state.required_resources == jsonable_encoder(mock_service_resources)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_repair_asks_rut_once_per_distinct_pricing_unit(
    *,
    client: TestClient,
    create_project: Callable[[str, dict[str, Any]], Awaitable[ProjectDict]],
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    project_db_cleaner: None,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    mocker: MockerFixture,
):
    """Every node of a start is repaired concurrently: nodes sharing a pricing unit share
    one request to RUT, so an unreachable RUT costs one request
    per distinct plan/unit instead of one per node.
    """
    assert client.app
    # created unlinked (this product does not bill here), then linked by hand to the same
    # unit: what a copy from another product leaves behind
    project = await create_project("repair-dedupe-project", _TWO_COMP_NODES_WORKBENCH)
    project_id = project["uuid"]
    for node_id in (_COMP_NODE_ID, _SECOND_COMP_NODE_ID):
        await set_node_pricing_link(
            sqlalchemy_async_engine,
            project_id,
            NodeID(node_id),
            pricing_plan_id=_DEFAULT_PRICING_PLAN_ID,
            pricing_unit_id=_DEFAULT_PRICING_UNIT_ID,
        )
    link_lookup = mocker.spy(_projects_service.rut_api, "get_pricing_plan_unit")

    await _repair(client, logged_user, project_id, osparc_product_name)

    assert link_lookup.call_count == 1


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_keeps_the_default_links_when_sizing_fails(
    client: TestClient,
    create_project: Callable[[str, dict[str, Any]], Awaitable[ProjectDict]],
    logged_user: UserInfoDict,
    sqlalchemy_async_engine: AsyncEngine,
    project_db_cleaner: None,
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_catalog_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_rut_default_pricing_unit: RutPricingUnitGet,
    mocked_director_v2_node_sizing: mock.AsyncMock,
    with_billed_product: None,
):
    """An unreachable director-v2 must not break project creation: every computational
    node keeps the DEFAULT unit it was linked to (the link is written before the sizing),
    keeps the catalog resources it was inserted with, and the nodes after the failing one
    are still processed. The next billed start completes the sizing (see the repair
    tests above).
    """
    assert client.app
    mocked_director_v2_node_sizing.side_effect = TimeoutError("director-v2 unreachable")

    new_project = await create_project("sizing-failure-project", _TWO_COMP_NODES_WORKBENCH)

    state = await get_node_pricing_state(sqlalchemy_async_engine, new_project["uuid"])
    # both computational nodes are linked to the default unit despite the failures, and
    # keep the catalog resources they were inserted with
    for node_id in (_COMP_NODE_ID, _SECOND_COMP_NODE_ID):
        node_state = state[NodeID(node_id)]
        assert node_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
        assert node_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
        assert node_state.required_resources == jsonable_encoder(mock_service_resources)

    # dynamic and frontend nodes are never linked at creation, failure or not
    for node_id in (_DYNAMIC_NODE_ID, _FILE_PICKER_NODE_ID):
        assert state[NodeID(node_id)].pricing_unit_id is None
