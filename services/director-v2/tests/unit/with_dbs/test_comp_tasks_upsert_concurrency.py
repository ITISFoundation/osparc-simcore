# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Deadlock between `upsert_tasks_from_project` and a concurrent webserver graph mutation

On 2026-10-09 production deadlocked (https://github.com/ITISFoundation/private-issues/issues/669):

    Process 29198 (director-v2): UPDATE projects_nodes SET required_resources=$1::JSONB ...
    Process 25497 (webserver):   UPDATE projects_nodes SET modified=now(), input_nodes=$1 ...
    CONTEXT:  while updating tuple (1480,1) in relation "projects"
        SQL statement "UPDATE projects SET last_change_date = NOW() WHERE uuid = project_uuid"

Every write to `projects_nodes` updates the single parent `projects` row through the
`projects_nodes_changed` trigger. The webserver locks that row before it touches any node, so
director-v2 must take it first too, otherwise each waits for a lock the other holds.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, NamedTuple
from unittest import mock

import pytest
import sqlalchemy as sa
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.api_schemas_resource_usage_tracker.pricing_plans import RutPricingUnitGet
from models_library.projects import NodesDict, ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo, PricingAndHardwareInfoTuple, UnitExtraInfoTier
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKey, ServiceMetaDataPublished, ServiceVersion
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    BootMode,
    ServiceResourcesDict,
)
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletInfo
from pydantic import ByteSize, PositiveInt, TypeAdapter
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_postgres_database.utils_projects_nodes import ProjectNode, ProjectNodesRepo
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.catalog import CatalogClient
from simcore_service_director_v2.modules.db.repositories.comp_tasks import CompTasksRepository
from simcore_service_director_v2.modules.db.repositories.comp_tasks._utils import (
    _CPUS_SAFE_MARGIN,
    _RAM_SAFE_MARGIN_RATIO,
)
from simcore_service_director_v2.modules.db.repositories.projects_nodes import ProjectsNodesRepository
from simcore_service_director_v2.modules.resource_usage_tracker_client import ResourceUsageTrackerClient
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]

_SERVICE_KEY = ServiceKey("simcore/services/comp/is4cpu")
_SERVICE_VERSION = ServiceVersion("1.0.0")
_EC2_INSTANCE_TYPE = "c5.xlarge"

# what the nodes ask for, less than what the machine of the pricing unit offers
_REQUESTED_CPUS = 1.0
_REQUESTED_RAM = 1024 * 1024 * 1024

_DEADLOCK_SQLSTATE = "40P01"
_TIMEOUT_S = 30.0

# the lock the webserver takes before it mutates the graph (see projects._projects_repository)
_LOCK_GRAPH_SQL = "SELECT uuid FROM projects WHERE uuid = :project_uuid FOR NO KEY UPDATE"
_SOMEONE_WAITS_FOR_A_LOCK_SQL = (
    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
)
_WAITERS_BEHIND_SQL = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid() AND :pid = ANY(pg_blocking_pids(pid))"
)


def _requested_resources() -> dict[str, Any]:
    """the resources of a single-container service, as stored in `projects_nodes`"""
    resources = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(
        {
            DEFAULT_SINGLE_SERVICE_NAME: {
                "image": f"{_SERVICE_KEY}:{_SERVICE_VERSION}",
                "resources": {
                    "CPU": {"limit": _REQUESTED_CPUS, "reservation": 0.1},
                    "RAM": {"limit": _REQUESTED_RAM, "reservation": 268435456},
                },
                "boot_modes": [BootMode.CPU],
            }
        }
    )
    dumped: dict[str, Any] = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).dump_python(resources, mode="json")
    return dumped


def _limits(required_resources: dict[str, Any]) -> tuple[float, int]:
    resources = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(required_resources)
    container = resources[DEFAULT_SINGLE_SERVICE_NAME].resources
    return float(container["CPU"].limit), int(container["RAM"].limit)


class _Project(NamedTuple):
    engine: AsyncEngine
    project_row: ProjectAtDB
    project_nodes: NodesDict
    node_ids: list[NodeID]
    user_id: UserID
    product_name: str

    @property
    def uuid(self) -> ProjectID:
        return self.project_row.uuid


@dataclass
class _CatalogGate:
    """A barrier inside the catalog call, which director-v2 makes while it holds its transaction

    `release` lets the test decide when the task creation may continue, i.e. how much time
    another client gets to change the project in between.
    """

    called: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)


@pytest.fixture
def catalog_gate() -> _CatalogGate:
    return _CatalogGate()


@pytest.fixture
def catalog_client(
    catalog_gate: _CatalogGate,
    fake_service_details: ServiceMetaDataPublished,
    fake_service_extras: ServiceExtras,
    fake_service_labels: dict[str, Any],
) -> CatalogClient:
    async def _get_service(
        user_id: UserID, service_key: ServiceKey, service_version: ServiceVersion, product_name: str
    ) -> dict[str, Any]:
        catalog_gate.called.set()
        await catalog_gate.release.wait()
        data_published = fake_service_details.model_copy(
            update={"key": service_key, "version": service_version}
        ).model_dump(by_alias=True)
        payload = ServiceGet.model_validate({**ServiceGet.model_json_schema()["examples"][0], **data_published})
        encoded: dict[str, Any] = jsonable_encoder(payload, by_alias=True)
        return encoded

    client: CatalogClient = mock.create_autospec(CatalogClient, instance=True)
    client.get_service.side_effect = _get_service
    client.get_service_extras.return_value = fake_service_extras
    client.get_service_labels.return_value = SimcoreServiceLabels.model_validate(fake_service_labels)
    return client


@pytest.fixture
def rut_client() -> ResourceUsageTrackerClient:
    """every node is priced on the same unit, whose machine is `_EC2_INSTANCE_TYPE`"""
    client: ResourceUsageTrackerClient = mock.create_autospec(ResourceUsageTrackerClient, instance=True)
    client.get_default_pricing_and_hardware_info.return_value = PricingAndHardwareInfoTuple(
        pricing_plan_id=1,
        pricing_unit_id=2,
        current_cost_per_unit_id=3,
        aws_ec2_instances=[_EC2_INSTANCE_TYPE],
    )
    client.get_pricing_unit.return_value = RutPricingUnitGet(
        pricing_unit_id=2,
        unit_name="SMALL",
        unit_extra_info=UnitExtraInfoTier(CPU=2, RAM=TypeAdapter(ByteSize).validate_python("4GiB"), VRAM=ByteSize(0)),
        current_cost_per_unit=Decimal(1),
        current_cost_per_unit_id=3,
        default=True,
        specific_info=HardwareInfo(aws_ec2_instances=[_EC2_INSTANCE_TYPE]),
    )
    return client


@pytest.fixture
def mocked_rpc_client() -> RabbitMQRPCClient:
    client: RabbitMQRPCClient = mock.create_autospec(RabbitMQRPCClient, instance=True)
    return client


@pytest.fixture
def mocked_clusters_keeper_get_instance_type_details(
    mocker: MockerFixture, fake_ec2_cpus: PositiveInt, fake_ec2_ram: ByteSize
) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.db.repositories.comp_tasks._utils.get_instance_type_details",
        return_value=[EC2InstanceTypeGet(name=_EC2_INSTANCE_TYPE, cpus=fake_ec2_cpus, ram=fake_ec2_ram)],
    )


@pytest.fixture
async def project(
    sqlalchemy_async_engine: AsyncEngine,
    create_registered_user: Callable[..., dict[str, Any]],
    with_product: dict[str, Any],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
) -> _Project:
    """a project of two computational nodes asking for less than the priced machine offers

    The task creation rewrites their `required_resources` from the size of that machine, i.e. it
    writes to `projects_nodes`.
    """
    user = create_registered_user()
    workbench = dict(sorted(fake_workbench_without_outputs.items())[:2])
    assert len(workbench) == 2

    created = await create_project(
        user,
        workbench=workbench,
        project_nodes_overrides={
            "key": _SERVICE_KEY,
            "version": _SERVICE_VERSION,
            "required_resources": _requested_resources(),
        },
    )
    project_nodes = await ProjectsNodesRepository(sqlalchemy_async_engine).get_all(project_id=created.uuid)
    assert len(project_nodes) == 2

    return _Project(
        engine=sqlalchemy_async_engine,
        project_row=created,
        project_nodes=project_nodes,
        node_ids=sorted(NodeID(node_id) for node_id in project_nodes),
        user_id=user["id"],
        product_name=f"{with_product['name']}",
    )


async def _wait_until(condition: Callable[[], Awaitable[bool]], what: str) -> None:
    async def _poll() -> None:
        while not await condition():  # noqa: ASYNC110  # polls the state of the database, no event to wait for
            await asyncio.sleep(0.05)

    try:
        await asyncio.wait_for(_poll(), timeout=_TIMEOUT_S)
    except TimeoutError:
        pytest.fail(what)


def _sqlstate(exc: BaseException) -> str | None:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(exc, "sqlstate", None)


async def _get_node(engine: AsyncEngine, project_uuid: ProjectID, node_id: NodeID) -> ProjectNode:
    async with engine.connect() as conn:
        return await ProjectNodesRepo(project_uuid=project_uuid).get(conn, node_id=node_id)


async def test_upsert_does_not_deadlock_with_a_concurrent_graph_mutation(
    project: _Project,
    catalog_gate: _CatalogGate,
    catalog_client: CatalogClient,
    rut_client: ResourceUsageTrackerClient,
    mocked_rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper_get_instance_type_details: mock.Mock,
    wallet_info: WalletInfo,
    fake_ec2_cpus: PositiveInt,
    fake_ec2_ram: ByteSize,
):
    graph_locked = asyncio.Event()

    async def _graph_mutation() -> None:
        # director-v2 is inside `upsert_tasks_from_project`, i.e. it read the project already
        await asyncio.wait_for(catalog_gate.called.wait(), timeout=_TIMEOUT_S)
        projects_nodes_repo = ProjectNodesRepo(project_uuid=project.uuid)
        async with project.engine.connect() as conn, conn.begin():
            # what the webserver does before touching any node, see run_project_graph_mutation
            await conn.execute(sa.text(_LOCK_GRAPH_SQL), {"project_uuid": f"{project.uuid}"})
            graph_locked.set()

            # Hold the lock until director-v2 either finished, i.e. it had to wait for this lock
            # before doing anything, or is stuck behind it halfway through its writes.
            holder = int(await conn.scalar(sa.text("SELECT pg_backend_pid()")))

            async def _director_v2_is_done_or_blocked() -> bool:
                if upsert.done():
                    return True
                async with project.engine.connect() as probe:
                    return bool(await probe.scalar(sa.text(_WAITERS_BEHIND_SQL), {"pid": holder}))

            await _wait_until(_director_v2_is_done_or_blocked, "director-v2 neither finished nor waited")

            # the nodes are written in the opposite order of director-v2's, as webserver did
            for node_id in reversed(project.node_ids):
                await projects_nodes_repo.update(conn, node_id=node_id, inputs={"changed_by": "webserver"})

    async def _graph_mutation_is_locked_or_queued() -> bool:
        if graph_locked.is_set():
            return True
        async with project.engine.connect() as probe:
            return bool(await probe.scalar(sa.text(_SOMEONE_WAITS_FOR_A_LOCK_SQL)))

    upsert: asyncio.Task[tuple[list[CompTaskAtDB], bool]] = asyncio.create_task(
        CompTasksRepository(project.engine).upsert_tasks_from_project(
            project=project.project_row,
            project_nodes=project.project_nodes,
            catalog_client=catalog_client,
            published_nodes=[],
            user_id=project.user_id,
            product_name=project.product_name,
            rut_client=rut_client,
            wallet_info=wallet_info,
            rabbitmq_rpc_client=mocked_rpc_client,
        )
    )
    mutation = asyncio.create_task(_graph_mutation())

    # the mutation either got the lock, or waits for director-v2 to release it: let the catalog
    # call return only then, so that director-v2 has to write the nodes while the mutation runs
    await asyncio.wait_for(catalog_gate.called.wait(), timeout=_TIMEOUT_S)
    await _wait_until(_graph_mutation_is_locked_or_queued, "the graph mutation neither locked nor queued")
    catalog_gate.release.set()

    # both run to the end, whichever way each of them ends, so that a deadlock shows up as a
    # failure of this test instead of cancelling the writer that survived it
    results = await asyncio.wait_for(asyncio.gather(upsert, mutation, return_exceptions=True), timeout=_TIMEOUT_S)
    failures = [result for result in results if isinstance(result, BaseException)]
    deadlock = next((exc for exc in failures if _sqlstate(exc) == _DEADLOCK_SQLSTATE), None)
    assert deadlock is None, f"deadlocked with the graph mutation: {deadlock}"
    assert not failures, f"unexpected failure: {failures}"

    (tasks, insufficient_credits), _ = results
    assert not insufficient_credits
    assert len(tasks) == len(project.node_ids)

    # both writers got their write in
    adjusted_cpus = fake_ec2_cpus - _CPUS_SAFE_MARGIN
    adjusted_ram = int(fake_ec2_ram - _RAM_SAFE_MARGIN_RATIO * fake_ec2_ram)
    for node_id in project.node_ids:
        node = await _get_node(project.engine, project.uuid, node_id)
        assert node.inputs == {"changed_by": "webserver"}
        assert _limits(node.required_resources) == pytest.approx((adjusted_cpus, adjusted_ram), rel=1e-6)
