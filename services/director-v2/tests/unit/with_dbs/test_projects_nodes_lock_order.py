# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=broad-exception-caught
"""Lock-ordering tests for `projects_nodes` writes.

These tests reproduce the production deadlock of 2026-10-09
(https://github.com/ITISFoundation/private-issues/issues/669) at the database level,
using the same two statements that PostgreSQL reported:

    Process 29198 (director-v2):
        UPDATE projects_nodes SET required_resources=$1::JSONB, modified=now()
        WHERE project_uuid=$2 AND node_id=$3
    Process 25497 (webserver):
        UPDATE projects_nodes SET modified=now(), input_nodes=$1, inputs=$2, ...
        WHERE project_uuid=$5 AND node_id=$6
    CONTEXT: while updating tuple (1480,1) in relation "projects"
        SQL statement "UPDATE projects SET last_change_date = NOW() WHERE uuid = project_uuid"
        PL/pgSQL function update_projects_last_change_date() line 11 at SQL statement

The contested object is the *single parent `projects` row*, which the
`projects_nodes_changed` trigger writes on **every** node write. Hence the invariant
enforced by these tests:

    every writer of `projects_nodes` must first lock the `projects` row
    (SELECT ... FOR NO KEY UPDATE) and must keep every transaction that writes a node
    row as short as possible, i.e. never span a call to another backend service.

The first two tests nail the PostgreSQL semantics the fix relies on, the last one checks
that director-v2's own task creation honours it.
"""

import asyncio
import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest
import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from models_library.users import UserID
from simcore_service_director_v2.modules.db.repositories.comp_tasks import CompTasksRepository, _utils
from simcore_service_director_v2.modules.db.repositories.projects_nodes import ProjectsNodesRepository
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]

_WS_APP_NAME = "test-webserver-style-writer"
_DIRECTOR_APP_NAME = "test-director-v2-style-writer"

# shortens the deadlock detector interval so the test does not wait the production 1s
_DEADLOCK_TIMEOUT_SQL: str = "SET LOCAL deadlock_timeout = '100ms'"
_DEADLOCK_SQLSTATE = "40P01"
_WAIT_TIMEOUT_S = 10.0

_lock_projects = sa.text("SELECT uuid FROM projects WHERE uuid = :project_uuid FOR NO KEY UPDATE")

# what director-v2 issues (see `_update_project_node_resources_from_hardware_info`)
# NOTE: CAST(...) is used instead of the `::` shorthand, which is ambiguous with bind parameters
_update_node_required_resources = sa.text(
    "UPDATE projects_nodes SET required_resources = CAST(:resources AS jsonb), modified = now() "
    "WHERE project_uuid = CAST(:project_uuid AS varchar) AND node_id = CAST(:node_id AS varchar)"
)

# what webserver issues (see `_projects_nodes_repository.update`)
_update_node_inputs = sa.text(
    "UPDATE projects_nodes SET modified = now(), inputs = CAST(:inputs AS jsonb) "
    "WHERE project_uuid = CAST(:project_uuid AS varchar) AND node_id = CAST(:node_id AS varchar)"
)


class _Project(NamedTuple):
    engine: AsyncEngine
    project_uuid: ProjectID
    node_ids: list[str]  # sorted, deterministic
    project_row: ProjectAtDB
    user_id: UserID
    product_name: str


def _is_deadlock(exc: BaseException | None) -> bool:
    """True for a PostgreSQL `deadlock_detected` (SQLSTATE 40P01), however the driver
    surfaced it (asyncpg's class is re-wrapped by SQLAlchemy's dialect)."""
    candidates: list[Any] = [exc] if exc is not None else []
    orig = getattr(exc, "orig", None)
    if orig is not None:
        candidates.append(orig)
    return any(
        getattr(candidate, "sqlstate", None) == _DEADLOCK_SQLSTATE
        or type(candidate).__name__ == "DeadlockDetectedError"
        for candidate in candidates
    )


def _types(results: list[Any]) -> list[Any]:
    return [
        (type(exc).__module__, type(exc).__name__, type(getattr(exc, "orig", type(exc))).__name__) for exc in results
    ]


@pytest.fixture
async def project(
    request: pytest.FixtureRequest,
    sqlalchemy_async_engine: AsyncEngine,
    create_registered_user,
    with_product: dict[str, Any],
    create_project,
    fake_workbench_without_outputs: dict[str, Any],
) -> Any:
    user = create_registered_user()
    workbench = dict(sorted(fake_workbench_without_outputs.items())[:2])
    assert len(workbench) == 2
    created = await create_project(user, workbench=workbench)

    async with sqlalchemy_async_engine.connect() as conn:
        trigger = await conn.scalar(
            sa.text(
                "SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                "WHERE t.tgname = 'projects_nodes_changed' AND c.relname = 'projects_nodes'"
            )
        )
    assert trigger, "the `projects_nodes_changed` trigger must exist to exercise lock ordering"

    return _Project(
        engine=sqlalchemy_async_engine,
        project_uuid=created.uuid,
        node_ids=sorted(f"{nid}" for nid in workbench),
        project_row=created,
        user_id=user["id"],
        product_name=f"{with_product['name']}",
    )


async def _begin(engine: AsyncEngine, application_name: str) -> tuple[Any, Any]:
    conn = await engine.connect()
    txn = await conn.begin()
    await conn.execute(sa.text(_DEADLOCK_TIMEOUT_SQL))
    # NOTE: `SET` does not accept bind parameters, hence `set_config`
    await conn.execute(
        sa.text("SELECT set_config('application_name', :app_name, true)"), {"app_name": application_name}
    )
    return conn, txn


async def _wait_until_blocked_on_lock(engine: AsyncEngine, application_name: str) -> None:
    """Waits until the backend identified by `application_name` is waiting on a lock."""
    async with engine.connect() as probe:
        for _ in range(int(_WAIT_TIMEOUT_S / 0.05)):
            row = (
                await probe.execute(
                    sa.text(
                        "SELECT wait_event_type FROM pg_stat_activity "
                        "WHERE application_name = :app_name AND pid <> pg_backend_pid()"
                    ),
                    {"app_name": application_name},
                )
            ).first()
            if row is not None and row.wait_event_type == "Lock":
                return
            await asyncio.sleep(0.05)
    pytest.fail(f"backend '{application_name}' never entered a lock wait")


async def test_webserver_and_director_v2_lock_orders_deadlock(project: _Project):
    """REPRODUCES the incident: webserver locks the `projects` row first, director-v2
    locks it last (through the `projects_nodes_changed` trigger). The resulting
    lock-order inversion makes PostgreSQL abort one of the two transactions.
    """
    engine, project_uuid, node_id = project.engine, project.project_uuid, project.node_ids[0]
    webserver_locked = asyncio.Event()
    results: list[Any] = [None, None]

    async def _director_v2_style_writer() -> None:
        conn, txn = await _begin(engine, _DIRECTOR_APP_NAME)
        try:
            await webserver_locked.wait()
            # locks the node row, then the AFTER trigger requests the `projects` row
            await conn.execute(
                _update_node_required_resources,
                {"project_uuid": f"{project_uuid}", "node_id": node_id, "resources": json.dumps({"container": {}})},
            )
            await txn.commit()
        except BaseException as exc:
            results[1] = exc
            await txn.rollback()
        finally:
            await conn.close()

    async def _webserver_style_writer() -> None:
        conn, txn = await _begin(engine, _WS_APP_NAME)
        try:
            # webserver graph mutations lock the project graph first
            await conn.execute(_lock_projects, {"project_uuid": f"{project_uuid}"})
            webserver_locked.set()
            # deterministic interleaving: director-v2 now holds the node row and is
            # blocked on the `projects` row held by this transaction
            await _wait_until_blocked_on_lock(engine, _DIRECTOR_APP_NAME)
            # requesting the row director-v2 holds closes the cycle
            await conn.execute(
                _update_node_inputs,
                {"project_uuid": f"{project_uuid}", "node_id": node_id, "inputs": json.dumps({})},
            )
            await txn.commit()
        except BaseException as exc:
            results[0] = exc
            await txn.rollback()
        finally:
            await conn.close()

    await asyncio.wait_for(
        asyncio.gather(_webserver_style_writer(), _director_v2_style_writer()),
        timeout=_WAIT_TIMEOUT_S,
    )
    assert any(_is_deadlock(exc) for exc in results), f"expected a deadlock, got {_types(results)}"


async def test_locking_projects_row_first_prevents_the_deadlock(project: _Project):
    """The lock-order fix: acquiring the `projects` row lock *before* writing nodes —
    like webserver does — serializes both transactions instead of cycling them.
    """
    engine, project_uuid, node_id = project.engine, project.project_uuid, project.node_ids[0]
    webserver_locked = asyncio.Event()
    results: list[Any] = [None, None]

    async def _director_v2_style_writer() -> None:
        conn, txn = await _begin(engine, _DIRECTOR_APP_NAME)
        try:
            await webserver_locked.wait()
            await conn.execute(_lock_projects, {"project_uuid": f"{project_uuid}"})
            await conn.execute(
                _update_node_required_resources,
                {"project_uuid": f"{project_uuid}", "node_id": node_id, "resources": json.dumps({"container": {}})},
            )
            await txn.commit()
        except BaseException as exc:
            results[1] = exc
            await txn.rollback()
        finally:
            await conn.close()

    async def _webserver_style_writer() -> None:
        conn, txn = await _begin(engine, _WS_APP_NAME)
        try:
            await conn.execute(_lock_projects, {"project_uuid": f"{project_uuid}"})
            webserver_locked.set()
            await asyncio.sleep(0.1)
            await conn.execute(
                _update_node_inputs,
                {"project_uuid": f"{project_uuid}", "node_id": node_id, "inputs": json.dumps({})},
            )
            await txn.commit()
        except BaseException as exc:
            results[0] = exc
            await txn.rollback()
        finally:
            await conn.close()

    await asyncio.wait_for(
        asyncio.gather(_webserver_style_writer(), _director_v2_style_writer()),
        timeout=_WAIT_TIMEOUT_S,
    )
    assert results == [None, None], f"unexpected failure: {results}"


@pytest.fixture
def recorded_statements(sqlalchemy_async_engine: AsyncEngine) -> Iterator[list[str]]:
    """Every statement issued on `sqlalchemy_async_engine`, in order.

    The stubbed service calls interleave a sentinel (see `_CATALOG_CALL`) in the same list,
    which makes the position of the service calls relative to the SQL statements observable.
    """
    statements: list[str] = []

    @event.listens_for(sqlalchemy_async_engine.sync_engine, "before_cursor_execute")
    def _record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(" ".join(statement.split()))

    try:
        yield statements
    finally:
        event.remove(sqlalchemy_async_engine.sync_engine, "before_cursor_execute", _record)


# sentinel appended by the stubbed catalog instead of a statement
_CATALOG_CALL = "<catalog call>"
# the statement the fix added to `upsert_tasks_from_project`, and everything it must precede
_PARENT_ROW_LOCK = ("FROM projects", "FOR NO KEY UPDATE")
_WRITES_UNDER_LOCK = ("UPDATE projects_nodes", "INSERT INTO comp_tasks", "DELETE FROM comp_tasks")


def _positions(statements: list[str], *, requires: tuple[str, ...]) -> list[int]:
    """positions of the statements containing every one of `requires`"""
    return [i for i, stmt in enumerate(statements) if all(needle in stmt for needle in requires)]


async def test_upsert_tasks_from_project_writes_only_after_the_service_calls(
    project: _Project,
    recorded_statements: list[str],
    monkeypatch: pytest.MonkeyPatch,
):
    """The fix, on the real code path: the rows are written only once every call to another
    backend service is over, and always after the `projects` row got locked.
    """

    # the catalog is the only service reached here (no wallet => no RUT/clusters-keeper)
    async def fake_get_node_infos(_client, _user_id, _product_name, _key_version):
        recorded_statements.append(_CATALOG_CALL)
        node_details = SimpleNamespace(model_dump=lambda **_kwargs: {"inputs": {}, "outputs": {}})
        return node_details, None, None

    async def fake_generate_task_image(**kwargs: Any):
        return _utils.Image(name=kwargs["node"].key, tag=kwargs["node"].version)

    monkeypatch.setattr(_utils, "_get_node_infos", fake_get_node_infos)
    monkeypatch.setattr(_utils, "_generate_task_image", fake_generate_task_image)

    tasks, _ = await CompTasksRepository(project.engine).upsert_tasks_from_project(
        project=project.project_row,
        project_nodes=await ProjectsNodesRepository(project.engine).get_all(project_id=project.project_uuid),
        catalog_client=SimpleNamespace(),
        published_nodes=[],
        user_id=project.user_id,
        product_name=project.product_name,
        rut_client=SimpleNamespace(),
        wallet_info=None,
        rabbitmq_rpc_client=SimpleNamespace(),
    )
    assert len(tasks) == len(project.node_ids)

    catalog_calls = [i for i, stmt in enumerate(recorded_statements) if stmt == _CATALOG_CALL]
    assert catalog_calls, "the catalog was never called"
    parent_row_locked = _positions(recorded_statements, requires=_PARENT_ROW_LOCK)
    assert parent_row_locked, "the parent `projects` row was never locked"
    writes = [i for i, stmt in enumerate(recorded_statements) if any(w in stmt for w in _WRITES_UNDER_LOCK)]
    assert writes, f"nothing was written, statements were: {recorded_statements}"

    assert max(catalog_calls) < min(parent_row_locked), "a service call was issued while a row was locked"
    assert min(parent_row_locked) < min(writes), "a row was written before the parent row was locked"
