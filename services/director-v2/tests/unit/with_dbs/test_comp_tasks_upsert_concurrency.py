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
from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest
import sqlalchemy as sa
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_resource_usage_tracker.pricing_plans import RutPricingUnitGet
from models_library.projects import NodesDict, ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    BootMode,
    ServiceResourcesDict,
)
from models_library.users import UserID
from models_library.wallets import WalletInfo
from pydantic import TypeAdapter
from simcore_postgres_database.utils_projects_nodes import ProjectNode, ProjectNodesRepo
from simcore_service_director_v2.modules.db.repositories.comp_tasks import (
    CompTasksRepository,
    _utils,
)
from simcore_service_director_v2.modules.db.repositories.projects_nodes import ProjectsNodesRepository
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]

_SERVICE_KEY = "simcore/services/comp/is4cpu"
_SERVICE_VERSION = "1.0.0"
_EC2_INSTANCE_TYPE = "c5.xlarge"

# what the nodes ask for, and what the machine of the pricing unit offers
_REQUESTED_CPUS = 2.0
_REQUESTED_RAM = 4 * 1024 * 1024 * 1024
_MACHINE_CPUS = 8.0
_MACHINE_RAM = 16 * 1024 * 1024 * 1024
_ADJUSTED_CPUS = _MACHINE_CPUS - 0.1  # `estimate_dask_worker_resources_from_ec2_instance` keeps a margin
_ADJUSTED_RAM = int(_MACHINE_RAM * 0.9)

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
    return TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).dump_python(resources, mode="json")


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
class _StubbedBackends:
    """The services the task creation calls, with a barrier inside the catalog call

    `release_backends` lets the test decide when the task creation may continue, i.e. how much
    time another client gets to change the project in between.
    """

    backends_called: asyncio.Event = field(default_factory=asyncio.Event)
    release_backends: asyncio.Event = field(default_factory=asyncio.Event)


@pytest.fixture
def wallet() -> WalletInfo:
    return WalletInfo(wallet_id=1, wallet_name="w", wallet_credit_amount=Decimal(100))


@pytest.fixture
def fake_rut_client() -> SimpleNamespace:
    """every node is priced on the same unit, whose machine offers `_MACHINE_CPUS` cpus"""

    async def get_default_pricing_and_hardware_info(_product_name, _key, _version):
        return (1, 2, 1, Decimal(1))

    async def get_pricing_unit(_product_name, _pricing_plan_id, pricing_unit_id):
        return RutPricingUnitGet(
            pricing_unit_id=pricing_unit_id,
            unit_name="SMALL",
            unit_extra_info={"CPU": 2, "RAM": "4GiB", "VRAM": "0"},
            current_cost_per_unit=Decimal(1),
            current_cost_per_unit_id=pricing_unit_id,
            default=True,
            specific_info=HardwareInfo(aws_ec2_instances=[_EC2_INSTANCE_TYPE]),
        )

    return SimpleNamespace(
        get_default_pricing_and_hardware_info=get_default_pricing_and_hardware_info,
        get_pricing_unit=get_pricing_unit,
    )


@pytest.fixture
async def project(
    sqlalchemy_async_engine: AsyncEngine,
    create_registered_user,
    with_product: dict[str, Any],
    create_project,
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


@pytest.fixture
def stubbed_backends(monkeypatch: pytest.MonkeyPatch) -> _StubbedBackends:
    """Replaces the catalog and clusters-keeper calls, the first catalog call waits for the test"""
    stubs = _StubbedBackends()

    async def fake_get_node_infos(_client, _user_id, _product_name, _key_version):
        stubs.backends_called.set()
        await stubs.release_backends.wait()
        node_details = SimpleNamespace(model_dump=lambda **_kwargs: {"inputs": {}, "outputs": {}})
        return node_details, None, None

    async def fake_get_instance_type_details(_rpc_client, *, instance_type_names):
        if _EC2_INSTANCE_TYPE not in instance_type_names:
            return []
        return [EC2InstanceTypeGet(name=_EC2_INSTANCE_TYPE, cpus=_MACHINE_CPUS, ram=_MACHINE_RAM)]

    async def fake_generate_task_image(**kwargs: Any):
        return _utils.Image(name=kwargs["node"].key, tag=kwargs["node"].version)

    monkeypatch.setattr(_utils, "_get_node_infos", fake_get_node_infos)
    monkeypatch.setattr(_utils, "_generate_task_image", fake_generate_task_image)
    monkeypatch.setattr(_utils, "get_instance_type_details", fake_get_instance_type_details)
    return stubs


async def _upsert_tasks(project: _Project, wallet: WalletInfo, rut_client: SimpleNamespace):
    return await CompTasksRepository(project.engine).upsert_tasks_from_project(
        project=project.project_row,
        project_nodes=project.project_nodes,
        catalog_client=SimpleNamespace(),
        published_nodes=[],
        user_id=project.user_id,
        product_name=project.product_name,
        rut_client=rut_client,
        wallet_info=wallet,
        rabbitmq_rpc_client=SimpleNamespace(),
    )


async def _wait_until(condition, what: str) -> None:
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
    stubbed_backends: _StubbedBackends,
    wallet: WalletInfo,
    fake_rut_client: SimpleNamespace,
):
    graph_locked = asyncio.Event()

    async def _graph_mutation() -> None:
        # director-v2 is inside `upsert_tasks_from_project`, i.e. it read the project already
        await asyncio.wait_for(stubbed_backends.backends_called.wait(), timeout=_TIMEOUT_S)
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

    upsert = asyncio.create_task(_upsert_tasks(project, wallet, fake_rut_client))
    mutation = asyncio.create_task(_graph_mutation())

    # the mutation either got the lock, or waits for director-v2 to release it: let the catalog
    # call return only then, so that director-v2 has to write the nodes while the mutation runs
    await asyncio.wait_for(stubbed_backends.backends_called.wait(), timeout=_TIMEOUT_S)
    await _wait_until(_graph_mutation_is_locked_or_queued, "the graph mutation neither locked nor queued")
    stubbed_backends.release_backends.set()

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
    for node_id in project.node_ids:
        node = await _get_node(project.engine, project.uuid, node_id)
        assert node.inputs == {"changed_by": "webserver"}
        assert _limits(node.required_resources) == pytest.approx((_ADJUSTED_CPUS, _ADJUSTED_RAM), rel=1e-6)
