# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Concurrency tests for the creation of a computational project's tasks.

On 2026-10-09 production deadlocked (https://github.com/ITISFoundation/private-issues/issues/669):
`CompTasksRepository.upsert_tasks_from_project` wrote `projects_nodes` while calling the catalog,
the resource-usage-tracker and the clusters-keeper, i.e. it kept the row locks of what it had
already written for as long as those calls took. A webserver graph mutation, which locks the
parent `projects` row before touching any node, then closed a lock cycle with it:

    Process 29198 (director-v2): UPDATE projects_nodes SET required_resources=$1::JSONB ...
    Process 25497 (webserver):   UPDATE projects_nodes SET modified=now(), input_nodes=$1 ...
    CONTEXT:  while updating tuple (1480,1) in relation "projects"
        SQL statement "UPDATE projects SET last_change_date = NOW() WHERE uuid = project_uuid"

The contested object is the *single parent `projects` row*, that the `projects_nodes_changed`
trigger updates on **every** write to `projects_nodes`. Two invariants follow, and both are
checked here on the real code path, i.e. by running `upsert_tasks_from_project` against a real
database while a webserver-style graph mutation runs concurrently:

    1. no write lock is held while a backend service is being called
    2. whatever another client changed in the meantime is not silently overwritten

`test_no_write_lock_is_held_while_the_backends_are_called` checks 1,
`test_upsert_does_not_deadlock_with_a_concurrent_graph_mutation` reproduces the incident of 1, and
`test_upsert_does_not_overwrite_a_node_changed_in_the_meantime` checks 2.
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
from simcore_service_director_v2.core.errors import ProjectNodesConcurrentlyUpdatedError
from simcore_service_director_v2.modules.db.repositories.comp_tasks import (
    CompTasksRepository,
    _utils,
)
from simcore_service_director_v2.modules.db.repositories.projects_nodes import ProjectsNodesRepository
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]

_SERVICE_KEY = "simcore/services/comp/is4cpu"
_SERVICE_VERSION = "1.0.0"
_EC2_INSTANCE_TYPE = "c5.xlarge"

# what the nodes ask for
_REQUESTED_CPUS = 2.0
_REQUESTED_RAM_GIB = 4
# what the machine the pricing unit points at offers, and what the task creation computes from it
# (`estimate_dask_worker_resources_from_ec2_instance` keeps a margin on both)
_MACHINE_CPUS = 8.0
_MACHINE_RAM = 16 * 1024 * 1024 * 1024
_ADJUSTED_CPUS = _MACHINE_CPUS - 0.1
_ADJUSTED_RAM = int(_MACHINE_RAM * 0.9)
# what a concurrent client asks for instead
_CONCURRENT_CPUS = 4.0

_DEADLOCK_SQLSTATE = "40P01"
_LOCK_NOT_AVAILABLE_SQLSTATE = "55P03"
_TIMEOUT_S = 30.0

# what the webserver issues before touching `projects_nodes` (see its
# projects._projects_repository._lock_project_graph), and the same with NOWAIT to only look
_LOCK_GRAPH_SQL = "SELECT uuid FROM projects WHERE uuid = :project_uuid FOR NO KEY UPDATE"
_TRY_LOCK_GRAPH_SQL = "SELECT uuid FROM projects WHERE uuid = :project_uuid FOR NO KEY UPDATE NOWAIT"

# who is waiting for a lock that the backend `pid` is holding
_WAITERS_BEHIND_SQL = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid() "
    "AND :pid = ANY(pg_blocking_pids(pid))"
)


def _resources(*, cpu: float = _REQUESTED_CPUS) -> dict[str, Any]:
    """the resources of a single-container service, as stored in `projects_nodes`"""
    return TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).dump_python(
        TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(
            {
                DEFAULT_SINGLE_SERVICE_NAME: {
                    "image": f"{_SERVICE_KEY}:{_SERVICE_VERSION}",
                    "resources": {
                        "CPU": {"limit": cpu, "reservation": 0.1},
                        "RAM": {"limit": _REQUESTED_RAM_GIB * 1024 * 1024 * 1024, "reservation": 268435456},
                    },
                    "boot_modes": [BootMode.CPU],
                }
            }
        ),
        mode="json",
    )


def _limits(required_resources: dict[str, Any]) -> tuple[float, int]:
    resources = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(required_resources)
    container = resources[DEFAULT_SINGLE_SERVICE_NAME].resources
    return float(container["CPU"].limit), int(container["RAM"].limit)


class _Project(NamedTuple):
    engine: AsyncEngine
    project_row: ProjectAtDB
    project_nodes: NodesDict
    node_ids: list[NodeID]  # sorted, like every write of director-v2 is
    user_id: UserID
    product_name: str

    @property
    def uuid(self) -> ProjectID:
        return self.project_row.uuid


@dataclass
class _StubbedBackends:
    """The services the task creation calls, with a barrier inside the catalog call

    `release_backends` lets the test decide when the task creation may continue, i.e. how much
    time another client gets to change the project in between. Every call records whether
    director-v2 was still holding the project's graph lock at that moment.
    """

    backends_called: asyncio.Event = field(default_factory=asyncio.Event)
    release_backends: asyncio.Event = field(default_factory=asyncio.Event)
    graph_lock_free_during_calls: list[bool] = field(default_factory=list)


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

    Their `required_resources` is what the task creation rewrites from the machine's size, i.e.
    the value that must neither be lost nor be written over another client's change.
    """
    user = create_registered_user()
    workbench = dict(sorted(fake_workbench_without_outputs.items())[:2])
    assert len(workbench) == 2

    created = await create_project(
        user,
        workbench=workbench,
        # NOTE: applies to every node, which all become the same computational service
        project_nodes_overrides={
            "key": _SERVICE_KEY,
            "version": _SERVICE_VERSION,
            "required_resources": _resources(),
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
def stubbed_backends(
    monkeypatch: pytest.MonkeyPatch,
    project: _Project,
) -> _StubbedBackends:
    """Replaces the catalog, resource-usage-tracker and clusters-keeper calls

    The catalog call also records whether director-v2 still held the project's graph lock at that
    moment, since holding it across those calls is what deadlocked with the webserver.
    """
    stubs = _StubbedBackends()

    async def fake_get_node_infos(_client, _user_id, _product_name, _key_version):
        stubs.graph_lock_free_during_calls.append(await _graph_lock_is_free(project.engine, project.uuid))
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
    # NOTE: same patch point as the comp_scheduler integration tests use
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


async def _wait_for(event: asyncio.Event, what: str) -> None:
    try:
        await asyncio.wait_for(event.wait(), timeout=_TIMEOUT_S)
    except TimeoutError:
        pytest.fail(what)


def _sqlstate(exc: BaseException) -> str | None:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(exc, "sqlstate", None)


def _is_deadlock(exc: BaseException | None) -> bool:
    return _sqlstate(exc) == _DEADLOCK_SQLSTATE


async def _graph_lock_is_free(engine: AsyncEngine, project_uuid: ProjectID) -> bool:
    """False when another transaction holds the project's graph lock

    `NOWAIT` makes that a lookup that never queues, so that the answer never changes what
    director-v2 is doing.
    """
    async with engine.connect() as conn:
        try:
            await conn.execute(sa.text(_TRY_LOCK_GRAPH_SQL), {"project_uuid": f"{project_uuid}"})
            return True
        except sa.exc.DBAPIError as exc:
            if _sqlstate(exc) != _LOCK_NOT_AVAILABLE_SQLSTATE:
                raise
            return False
        finally:
            await conn.rollback()


async def _backend_pid(conn: AsyncConnection) -> int:
    return int(await conn.scalar(sa.text("SELECT pg_backend_pid()")))


async def _wait_until_blocked_behind(engine: AsyncEngine, pid: int) -> None:
    """waits until another transaction is waiting for a lock that `pid` holds"""
    stmt = sa.text(_WAITERS_BEHIND_SQL).bindparams(sa.bindparam("pid", type_=sa.Integer))
    async with engine.connect() as probe:
        for _ in range(int(_TIMEOUT_S / 0.05)):
            if await probe.scalar(stmt, {"pid": pid}):
                return
            await asyncio.sleep(0.05)
    pytest.fail(f"nobody waited behind the graph lock held by backend {pid}")


async def _get_node(engine: AsyncEngine, project_uuid: ProjectID, node_id: NodeID) -> ProjectNode:
    async with engine.connect() as conn:
        return await ProjectNodesRepo(project_uuid=project_uuid).get(conn, node_id=node_id)


async def test_no_write_lock_is_held_while_the_backends_are_called(
    project: _Project,
    stubbed_backends: _StubbedBackends,
    wallet: WalletInfo,
    fake_rut_client: SimpleNamespace,
):
    """Invariant 1: no write lock is held across a call to another backend service

    This is what the fix consists of: the writes that used to happen in the transaction calling
    the catalog/resource-usage-tracker/clusters-keeper now happen in a short transaction of their
    own, so that no lock can be held while waiting for another service. Since every write to
    `projects_nodes` reaches the parent `projects` row through the trigger, that row tells
    whether a write transaction is still open.
    """
    stubbed_backends.release_backends.set()

    tasks, insufficient_credits = await _upsert_tasks(project, wallet, fake_rut_client)

    assert not insufficient_credits
    assert len(tasks) == len(project.node_ids)
    assert stubbed_backends.graph_lock_free_during_calls, "the backends were never called"
    n_held = stubbed_backends.graph_lock_free_during_calls.count(False)
    assert n_held == 0, (
        f"director-v2 held a write lock across {n_held} of "
        f"{len(stubbed_backends.graph_lock_free_during_calls)} backend calls, i.e. it kept those "
        "row locks while waiting for another service, which is what deadlocked with the webserver"
    )

    # the write really happened, i.e. the test did exercise the interesting path
    for node_id in project.node_ids:
        node = await _get_node(project.engine, project.uuid, node_id)
        assert _limits(node.required_resources) == pytest.approx((_ADJUSTED_CPUS, _ADJUSTED_RAM), rel=1e-6)


async def test_upsert_does_not_deadlock_with_a_concurrent_graph_mutation(
    project: _Project,
    stubbed_backends: _StubbedBackends,
    wallet: WalletInfo,
    fake_rut_client: SimpleNamespace,
):
    """Invariant 1 as it took production down: a graph mutation runs while the tasks are made

    The mutation locks the `projects` row and then writes the nodes in the reverse order that
    director-v2 writes them in, which is what closed the lock cycle: director-v2 held a node row
    the mutation needed while the mutation held the parent row director-v2 needed, and PostgreSQL
    aborted one of the two. Director-v2 must instead wait for the parent row *before* writing
    anything, so that the two can never hold locks the other waits for.
    """
    graph_locked = asyncio.Event()

    async def _graph_mutation() -> None:
        # director-v2 is inside `upsert_tasks_from_project`, i.e. it read the project already
        await _wait_for(stubbed_backends.backends_called, "the backends were never called")
        projects_nodes_repo = ProjectNodesRepo(project_uuid=project.uuid)
        async with project.engine.connect() as conn, conn.begin():
            # what the webserver does before touching any node, see run_project_graph_mutation
            await conn.execute(sa.text(_LOCK_GRAPH_SQL), {"project_uuid": f"{project.uuid}"})
            holder = await _backend_pid(conn)
            graph_locked.set()

            # director-v2 is now waiting for the row this transaction holds
            await _wait_until_blocked_behind(project.engine, holder)

            # and now writes the nodes in the order that deadlocked with director-v2
            for node_id in reversed(project.node_ids):
                await projects_nodes_repo.update(conn, node_id=node_id, inputs={"changed_by": "webserver"})

    mutation = asyncio.create_task(_graph_mutation())
    upsert = asyncio.create_task(_upsert_tasks(project, wallet, fake_rut_client))

    await _wait_for(graph_locked, "the graph mutation never locked the project")
    stubbed_backends.release_backends.set()

    # both writers run to the end, whichever way each of them ends, so that a deadlock shows up
    # as a failure of this test instead of cancelling the writer that survived it
    results = await asyncio.wait_for(asyncio.gather(upsert, mutation, return_exceptions=True), timeout=_TIMEOUT_S)
    failures = [result for result in results if isinstance(result, BaseException)]
    deadlock = next((exc for exc in failures if _is_deadlock(exc)), None)
    assert deadlock is None, f"deadlocked with the graph mutation: {deadlock}"
    assert not failures, f"unexpected failure: {failures}"

    (tasks, insufficient_credits), _ = results
    assert not insufficient_credits
    assert len(tasks) == len(project.node_ids)

    # and both writers got their write in
    for node_id in project.node_ids:
        node = await _get_node(project.engine, project.uuid, node_id)
        assert node.inputs == {"changed_by": "webserver"}
        assert _limits(node.required_resources) == pytest.approx((_ADJUSTED_CPUS, _ADJUSTED_RAM), rel=1e-6)


async def test_upsert_does_not_overwrite_a_node_changed_in_the_meantime(
    project: _Project,
    stubbed_backends: _StubbedBackends,
    wallet: WalletInfo,
    fake_rut_client: SimpleNamespace,
):
    """Invariant 2: values computed before the backends were called are not written back blindly

    The tasks are computed from a snapshot taken before any backend is called, so whatever another
    client changes of it in the meantime is invisible to them. Reporting a conflict is then the
    only safe answer: writing those values back would silently undo that client's change, and a
    node deleted in the meantime would get a task that nothing would ever run.
    """
    change_written = asyncio.Event()
    node_id = project.node_ids[0]

    async def _another_client() -> None:
        # the snapshot the tasks are being computed from predates this write, which is exactly
        # the situation the guard has to notice
        await _wait_for(stubbed_backends.backends_called, "the backends were never called")
        async with project.engine.connect() as conn, conn.begin():
            await conn.execute(sa.text(_LOCK_GRAPH_SQL), {"project_uuid": f"{project.uuid}"})
            await ProjectNodesRepo(project_uuid=project.uuid).update(
                conn, node_id=node_id, required_resources=_resources(cpu=_CONCURRENT_CPUS)
            )
        change_written.set()

    another_client = asyncio.create_task(_another_client())
    upsert = asyncio.create_task(_upsert_tasks(project, wallet, fake_rut_client))

    await _wait_for(change_written, "the concurrent change was never written")
    stubbed_backends.release_backends.set()

    results = await asyncio.wait_for(asyncio.gather(upsert, another_client, return_exceptions=True), timeout=_TIMEOUT_S)
    assert isinstance(results[0], ProjectNodesConcurrentlyUpdatedError), (
        f"the concurrent change went unnoticed: {results}"
    )

    # the other client's value survived, i.e. the conflict is not just reported but also real
    node = await _get_node(project.engine, project.uuid, node_id)
    assert _limits(node.required_resources)[0] == pytest.approx(_CONCURRENT_CPUS)

    # and retrying now that nothing is in flight succeeds
    tasks, insufficient_credits = await _upsert_tasks(project, wallet, fake_rut_client)
    assert not insufficient_credits
    assert len(tasks) == len(project.node_ids)
    node = await _get_node(project.engine, project.uuid, node_id)
    assert _limits(node.required_resources) == pytest.approx((_ADJUSTED_CPUS, _ADJUSTED_RAM), rel=1e-6)
