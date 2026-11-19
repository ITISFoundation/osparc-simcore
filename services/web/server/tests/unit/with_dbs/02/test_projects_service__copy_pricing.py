# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Characterization tests for the pricing state (`pricing_plan_id`, `pricing_unit_id` and
the sized `required_resources`) that `clone_project_data` and
`_copy_project_nodes_from_source_project` in `_projects_service.py` give to the nodes of a
copied or cloned project, and for the repair of a link copied while the
resource-usage-tracker did not answer.

They pin the state of the DB after a copy — which link a node ends up with, which nodes the
web-server sizes, how often the tracker is asked — and not the code that produces it.
"""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Annotated, Any, Final

import pytest
from _projects_copy_common import _fetch_source_project, _get_inserted_nodes
from aiohttp import web
from aiohttp.test_utils import TestClient
from annotated_types import doc  # pyright: ignore[reportAttributeAccessIssue]
from celery_library.async_jobs import AsyncJobResultUpdate
from common_library.users_enums import UserRole
from faker import Faker
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobStatus
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_mock import MockerFixture, MockType
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.project_nodes_pricing import (
    R5_4XLARGE_NAME,
    get_node_pricing_state,
    make_pricing_unit,
    regex_for_rut_pricing_unit,
    resources_limits,
    set_node_pricing_link,
    set_node_required_resources,
    single_container_required_resources,
)
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.utils_projects_nodes import ProjectNode
from simcore_service_webserver.projects import (
    _projects_repository as projects_repository,
)
from simcore_service_webserver.projects import _projects_service
from simcore_service_webserver.projects._crud_api_create import (
    _compose_project_data,
)
from simcore_service_webserver.projects._projects_service import (
    clone_project_data,
    copy_allow_guests_to_push_states_and_output_ports,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.utils import NodesMap
from simcore_service_webserver.resource_usage.settings import (
    get_plugin_settings as get_rut_plugin_settings,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
]


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def fake_project(fake_project: ProjectDict, workbench_db_column: dict[str, Any]) -> ProjectDict:
    # OVERRIDES session-level `fake_project`: use a workbench with interconnected
    # nodes (port links + input_nodes) so remap logic can be exercised end-to-end.
    project = deepcopy(fake_project)
    project["workbench"] = workbench_db_column
    return project


@pytest.fixture
def task_progress() -> TaskProgress:
    return TaskProgress.create()


@pytest.fixture
async def storage_subsystem_mock_override(mocker: MockerFixture, faker: Faker) -> None:
    """Mocks `storage_service.copy_data_folders_from_project` used by `clone_project_data`.

    NOTE: this is a DIFFERENT patch target than the `storage_subsystem_mock` fixture
    (which patches `_crud_api_create.copy_data_folders_from_project`, used by `create_project`).
    """
    mock_fn = mocker.patch(
        "simcore_service_webserver.projects._projects_service.storage_service.copy_data_folders_from_project",
        autospec=True,
    )

    async def _mock_copy(
        app: web.Application,
        *,
        source_project: ProjectDict,
        destination_project: ProjectDict,
        nodes_map: NodesMap,
        user_id: UserID,
        product_name: str,
    ):
        yield AsyncJobResultUpdate(
            AsyncJobStatus(
                job_id=faker.uuid4(cast_to=None),
                progress=ProgressReport(actual_value=0),
                done=False,
            )
        )

        async def _mock_result() -> None:
            return None

        yield AsyncJobResultUpdate(
            AsyncJobStatus(
                job_id=faker.uuid4(cast_to=None),
                progress=ProgressReport(actual_value=1),
                done=True,
            ),
            _mock_result(),
        )

    mock_fn.side_effect = _mock_copy


#
# CHARACTERIZATION TESTS (pin the state of the DB, not the code that produces it)
#


_SOURCED_SIZED_RESOURCES: Final[
    Annotated[
        dict[str, Any],
        doc(
            "a comp node sized for r5.4xlarge (16 CPU / 128 GiB) with the dask-worker formula:"
            " cpu = 16 - 0.1 = 15.9, ram = int(128 GiB * 0.9) = 123695058124"
        ),
    ]
] = single_container_required_resources("simcore/services/comp/itis/sleeper", cpu=15.9, ram_bytes=123695058124)
_PRICING_PLAN_ID: Final[Annotated[int, doc("a plan the product knows, not its default")]] = 1
_PRICING_UNIT_ID: Final[int] = 2

# the unit mocked by `mock_rut_default_pricing_unit` (t3.medium): 1.9 CPU, 3865470566 RAM bytes
_DEFAULT_PRICING_PLAN_ID: Final[int] = 1
_DEFAULT_PRICING_UNIT_ID: Final[int] = 1


def _sleeper_node(nodes: dict[NodeID, ProjectNode]) -> ProjectNode:
    # the workbench fixture has TWO comp sleepers; pin one deterministically by label
    return next(node for node in nodes.values() if node.label == "sleeper")


async def _price_and_size_one_comp_node(
    app: web.Application, engine: AsyncEngine, project_uuid: str
) -> tuple[str, dict[str, Any]]:
    """Directly (no endpoints) gives the project a comp node with a non-default
    pricing-unit link and hand-sized `required_resources`.
    """
    nodes = await _get_inserted_nodes(app, project_uuid)
    comp_node = _sleeper_node(nodes)
    await set_node_pricing_link(
        engine,
        project_uuid,
        f"{comp_node.node_id}",
        pricing_plan_id=_PRICING_PLAN_ID,
        pricing_unit_id=_PRICING_UNIT_ID,
    )
    await set_node_required_resources(engine, project_uuid, f"{comp_node.node_id}", _SOURCED_SIZED_RESOURCES)
    return f"{comp_node.node_id}", _SOURCED_SIZED_RESOURCES


async def _assert_clone_pricing_state(
    app: web.Application,
    engine: AsyncEngine,
    cloned_project: ProjectDict,
    expected_resources: dict[str, Any],
) -> None:
    state = await get_node_pricing_state(engine, cloned_project["uuid"])
    assert len(state) == len(cloned_project["workbench"])
    nodes = await _get_inserted_nodes(app, cloned_project["uuid"])

    # the source's pricing link is copied (validated against this product) and the
    # source's hand-sized `required_resources` are kept verbatim — NOT re-sized
    comp_node = _sleeper_node(nodes)
    priced_state = state[comp_node.node_id]
    assert priced_state.pricing_plan_id == _PRICING_PLAN_ID
    assert priced_state.pricing_unit_id == _PRICING_UNIT_ID
    assert priced_state.required_resources == expected_resources

    # a comp node without a source link gets the DEFAULT unit and is sized with the
    # dask-worker formula of that unit's machine
    second_comp_node = next(node for node in nodes.values() if node.label == "sleeper_2")
    default_state = state[second_comp_node.node_id]
    assert default_state.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert default_state.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    # sizing rewrites the resources and keeps the rest of the payload (image...)
    assert default_state.required_resources
    sized = default_state.required_resources["container"]["resources"]
    assert sized == resources_limits(cpu=1.9, ram_bytes=3865470566)

    # frontend nodes get no link
    for node in nodes.values():
        if f"{node.key}".startswith("simcore/services/frontend/"):
            node_state = state[node.node_id]
            assert node_state.pricing_plan_id is None
            assert node_state.pricing_unit_id is None


@pytest.mark.parametrize("source_kind", ["standard_project", "template"])
async def test_clone_project_data_copies_pricing_links_and_sizes_unlinked_comp_nodes(
    source_kind: str,
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    template_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mock_rut_default_pricing_unit: None,
    mocked_director_v2_node_sizing: MockType,
    with_billed_product: None,
):
    """Cloning a project or a template in a billed product copies the source pricing links
    after validating them against the destination product, and keeps the source
    `required_resources` verbatim. A comp node without a source link gets the product's
    default unit and is sized with that machine's dask-worker formula. Frontend nodes get
    no link.
    """
    assert client.app
    source = template_project if source_kind == "template" else user_project
    source_uuid = source["uuid"]

    # SETUP: source comp node is linked to a non-default unit and sized
    _, sourced_resources = await _price_and_size_one_comp_node(client.app, sqlalchemy_async_engine, source_uuid)

    # the resource-usage-tracker knows the source's non-default unit (copy validation asks for it)
    settings = get_rut_plugin_settings(client.app)
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID),
        payload=jsonable_encoder(
            make_pricing_unit(
                pricing_unit_id=_PRICING_UNIT_ID,
                default=False,
                aws_ec2_instance=R5_4XLARGE_NAME,
            )
        ),
        repeat=True,
    )

    # ACT
    source_project = await _fetch_source_project(client.app, source_uuid, UserID(logged_user["id"]))
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )

    # only the newly default-linked computational node is sized (the copied link
    # keeps the source's resources verbatim)
    mocked_director_v2_node_sizing.assert_called_once()

    # ASSERT: the clone's DB state
    await _assert_clone_pricing_state(client.app, sqlalchemy_async_engine, cloned_project, sourced_resources)

    # the SOURCE project keeps its link and resources untouched
    source_state = await get_node_pricing_state(sqlalchemy_async_engine, source_uuid)
    linked = {
        node_id: node_state for node_id, node_state in source_state.items() if node_state.pricing_unit_id is not None
    }
    assert len(linked) == 1
    (source_node_state,) = linked.values()
    assert source_node_state.pricing_plan_id == _PRICING_PLAN_ID
    assert source_node_state.required_resources == sourced_resources


async def test_copy_allow_guests_to_push_states_and_output_ports_keeps_disabled_when_source_disabled(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    shared_project: ProjectDict,
):
    # SETUP
    assert client.app
    source_uuid = user_project["uuid"]
    destination_uuid = shared_project["uuid"]

    assert (
        await projects_repository.allows_guests_to_push_states_and_output_ports(client.app, project_uuid=source_uuid)
        is False
    )

    # ACT
    await copy_allow_guests_to_push_states_and_output_ports(
        client.app,
        from_project_uuid=source_uuid,
        to_project_uuid=destination_uuid,
    )

    # ASSERT
    assert (
        await projects_repository.allows_guests_to_push_states_and_output_ports(
            client.app, project_uuid=destination_uuid
        )
        is False
    )


@pytest.mark.parametrize(
    "rut_answer, copied_link",
    [
        pytest.param(
            {
                "payload": jsonable_encoder(
                    make_pricing_unit(pricing_unit_id=_PRICING_UNIT_ID, default=False, aws_ec2_instance=R5_4XLARGE_NAME)
                )
            },
            (_PRICING_PLAN_ID, _PRICING_UNIT_ID),
            id="the product knows the unit",
        ),
        pytest.param({"status": status.HTTP_404_NOT_FOUND}, (None, None), id="unknown in the product"),
        pytest.param({"status": status.HTTP_503_SERVICE_UNAVAILABLE}, (_PRICING_PLAN_ID, _PRICING_UNIT_ID), id="503"),
        pytest.param({"exception": TimeoutError}, (_PRICING_PLAN_ID, _PRICING_UNIT_ID), id="no answer"),
    ],
)
async def test_copy_pricing_links_asks_rut_once_per_unit_and_copies_what_it_can(
    rut_answer: dict[str, Any],
    copied_link: tuple[int | None, int | None],
    client: TestClient,
    clear_pricing_lookup_caches: None,
    user_project: ProjectDict,
    shared_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mocker: MockerFixture,
    with_billed_product: None,
):
    """Several nodes of a project typically share one pricing unit: the copy asks the
    resource-usage-tracker about every distinct plan/unit once, not once per node,
    which an unreachable one would otherwise pay for with one timeout per node. A unit the
    product does not know is not copied (the caller links the destination's default
    instead); one it could not confirm is copied rather than lost, and the copy succeeds
    either way.
    """
    assert client.app
    # both projects were inserted from the same workbench, so their node ids match
    nodes_map: NodesMap = {
        node_id: node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"]
    }
    assert len(nodes_map) > 1

    for node_id in nodes_map:
        await set_node_pricing_link(
            sqlalchemy_async_engine,
            user_project["uuid"],
            node_id,
            pricing_plan_id=_PRICING_PLAN_ID,
            pricing_unit_id=_PRICING_UNIT_ID,
        )
    settings = get_rut_plugin_settings(client.app)
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID),
        repeat=True,
        **rut_answer,
    )
    validate_link = mocker.spy(_projects_service.rut_api, "get_pricing_plan_unit")

    await _projects_service.copy_pricing_links(
        client.app,
        source_project_id=ProjectID(user_project["uuid"]),
        destination_project_id=ProjectID(shared_project["uuid"]),
        nodes_map=nodes_map,
        product_name=osparc_product_name,
    )

    # one request for the distinct plan/unit, failures memoized like successes
    assert validate_link.call_count == 1
    destination_state = await get_node_pricing_state(sqlalchemy_async_engine, shared_project["uuid"])
    for node_id in nodes_map:
        node_state = destination_state[NodeID(node_id)]
        assert (node_state.pricing_plan_id, node_state.pricing_unit_id) == copied_link


async def test_copy_pricing_links_copies_nothing_in_a_product_that_does_not_bill(
    client: TestClient,
    clear_pricing_lookup_caches: None,
    user_project: ProjectDict,
    shared_project: ProjectDict,
    osparc_product_name: ProductName,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mocker: MockerFixture,
):
    """Copying in a product that does not bill for its nodes' resources copies no
    pricing link, which is what keeps the copied nodes' resources writable through
    `PUT .../nodes/{node_id}/resources`. The resource-usage-tracker is not asked.
    """
    assert client.app
    nodes_map: NodesMap = {
        node_id: node_id for node_id, node in user_project["workbench"].items() if "/comp/" in node["key"]
    }
    for node_id in nodes_map:
        await set_node_pricing_link(
            sqlalchemy_async_engine,
            user_project["uuid"],
            node_id,
            pricing_plan_id=_PRICING_PLAN_ID,
            pricing_unit_id=_PRICING_UNIT_ID,
        )
    asked_rut = mocker.spy(_projects_service.rut_api, "get_pricing_plan_unit")

    await _projects_service.copy_pricing_links(
        client.app,
        source_project_id=ProjectID(user_project["uuid"]),
        destination_project_id=ProjectID(shared_project["uuid"]),
        nodes_map=nodes_map,
        product_name=osparc_product_name,
    )

    asked_rut.assert_not_called()
    destination_state = await get_node_pricing_state(sqlalchemy_async_engine, shared_project["uuid"])
    for node_id in nodes_map:
        node_state = destination_state[NodeID(node_id)]
        assert node_state.pricing_plan_id is None
        assert node_state.pricing_unit_id is None


async def test_a_link_copied_during_a_rut_outage_is_repaired_on_the_next_billed_start(
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    osparc_product_name: ProductName,
    task_progress: TaskProgress,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    storage_subsystem_mock_override: None,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    mock_rut_default_pricing_unit: None,
    mocked_director_v2_node_sizing: MockType,
    with_billed_product: None,
):
    """Copying while the resource-usage-tracker is unreachable keeps the source's link and the resources
    sized for it, so the copy costs nothing it cannot recover. If that link turns out not
    to exist in the destination product, the next billed start replaces it with the
    destination's default unit and sizes the node for it, instead of leaving the node
    unusable for every run.
    """
    assert client.app
    source_uuid = user_project["uuid"]
    _, sourced_resources = await _price_and_size_one_comp_node(client.app, sqlalchemy_async_engine, source_uuid)
    settings = get_rut_plugin_settings(client.app)
    source_link_url = regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID)
    # unreachable during the copy, and unknown in this product afterwards
    aioresponses_mocker.get(source_link_url, exception=TimeoutError)
    aioresponses_mocker.get(source_link_url, status=status.HTTP_404_NOT_FOUND, repeat=True)

    source_project = await _fetch_source_project(client.app, source_uuid, UserID(logged_user["id"]))
    cloned_project = await clone_project_data(
        client.app,
        source_project=source_project,
        forced_copy_project_id=None,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        product_api_base_url="http://product.testserver.io",
        task_progress=task_progress,
    )
    cloned_uuid = ProjectID(cloned_project["uuid"])
    copied_node_id = f"{_sleeper_node(await _get_inserted_nodes(client.app, f'{cloned_uuid}')).node_id}"

    # the copy kept the link it could not confirm, and the resources sized for it
    state = await get_node_pricing_state(sqlalchemy_async_engine, cloned_uuid)
    copied = state[NodeID(copied_node_id)]
    assert copied.pricing_plan_id == _PRICING_PLAN_ID
    assert copied.pricing_unit_id == _PRICING_UNIT_ID
    assert copied.required_resources == sourced_resources

    await _projects_service.repair_projects_nodes_pricing_and_resources(
        client.app,
        user_id=UserID(logged_user["id"]),
        project_ids=[cloned_uuid],
        product_name=osparc_product_name,
    )

    # the next billed start replaces the link the product does not know, and sizes for the
    # unit it links instead
    state = await get_node_pricing_state(sqlalchemy_async_engine, cloned_uuid)
    repaired = state[NodeID(copied_node_id)]
    assert repaired.pricing_plan_id == _DEFAULT_PRICING_PLAN_ID
    assert repaired.pricing_unit_id == _DEFAULT_PRICING_UNIT_ID
    assert repaired.required_resources
    assert repaired.required_resources["container"]["resources"] == resources_limits(cpu=1.9, ram_bytes=3865470566)


async def test_compose_project_data_of_a_copy_says_nothing_about_the_nodes(
    client: TestClient,
    logged_user: UserInfoDict,
    osparc_product_name: ProductName,
    faker: Faker,
):
    """Overriding fields of a copy (its name, e.g. when an api-server job renames it)
    must not replace the nodes prepared from the source project: the caller keeps the
    source's `required_resources` (and the pricing links copied on top of them).
    """
    assert client.app
    new_project, project_nodes = await _compose_project_data(
        client.app,
        user_id=UserID(logged_user["id"]),
        product_name=osparc_product_name,
        new_project={"uuid": f"{faker.uuid4()}", "name": "copy of source", "description": "from the source"},
        predefined_project={"name": "renamed copy", "description": None},
    )

    assert project_nodes is None
    assert new_project["name"] == "renamed copy"
    # a field the override leaves empty keeps the source project's value
    assert new_project["description"] == "from the source"


async def test_creating_a_copy_with_a_name_override_through_the_endpoint_keeps_the_priced_nodes(
    *,
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    sqlalchemy_async_engine: AsyncEngine,
    aioresponses_mocker: AioResponsesMock,
    storage_subsystem_mock: Any,
    project_db_cleaner: None,
    mocked_dynamic_services_interface: dict[str, MockType],
    mock_dynamic_scheduler: None,
    mock_rut_default_pricing_unit: None,
    mocked_director_v2_node_sizing: MockType,
    with_billed_product: None,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    """The same override through `POST /v0/projects?from_study=...`: a body that renames the
    copy says nothing about its nodes, so the copy carries the source's pricing link and the
    resources sized for it, on one node row per source node.
    """
    assert client.app
    _, sourced_resources = await _price_and_size_one_comp_node(
        client.app, sqlalchemy_async_engine, user_project["uuid"]
    )
    settings = get_rut_plugin_settings(client.app)
    aioresponses_mocker.get(
        regex_for_rut_pricing_unit(f"{settings.api_base_url}", _PRICING_PLAN_ID, _PRICING_UNIT_ID),
        payload=jsonable_encoder(
            make_pricing_unit(pricing_unit_id=_PRICING_UNIT_ID, default=False, aws_ec2_instance=R5_4XLARGE_NAME)
        ),
        repeat=True,
    )

    new_project = await request_create_project(
        client,
        status.HTTP_202_ACCEPTED,
        status.HTTP_201_CREATED,
        logged_user,
        primary_group,
        project={"name": "renamed copy"},
        from_study=user_project,
        copy_data=False,
    )

    assert new_project["name"] == "renamed copy"
    state = await get_node_pricing_state(sqlalchemy_async_engine, new_project["uuid"])
    assert len(state) == len(new_project["workbench"])

    copied_link = [node_state for node_state in state.values() if node_state.pricing_unit_id == _PRICING_UNIT_ID]
    assert len(copied_link) == 1
    (copied,) = copied_link
    assert copied.pricing_plan_id == _PRICING_PLAN_ID
    assert copied.required_resources == sourced_resources
