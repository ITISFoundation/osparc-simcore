# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments
# pylint:disable=protected-access

import asyncio
import datetime as dt
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
import sqlalchemy as sa
import sqlalchemy.exc as sa_exc
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectAtDB
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.webserver_models import DB_OUTBOX_KIND_COMP_TASK_SYNC
from simcore_service_webserver.db_listener._repository import (
    MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT,
)
from simcore_service_webserver.db_listener._service import (
    _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN,
    _claim_and_process_aggregate,
    _claim_and_process_one_outbox_event,
    claim_and_process_outbox_events,
)
from simcore_service_webserver.db_listener._task import (
    _OUTBOX_LISTENER_APPLICATION_NAME,
    _with_outbox_wakeup_listener,
)
from simcore_service_webserver.db_listener.models import ClaimableAggregate
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import func

_COUNT_LISTENER_CONNECTIONS_SQL = (
    "select count(*) from pg_stat_activity where application_name like :pattern and pid != pg_backend_pid()"
)


@pytest.fixture
async def mock_project_subsystem(mocker: MockerFixture) -> dict[str, mock.Mock]:
    mocked_project_calls = {}

    mocked_project_calls["update_node_outputs"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.update_node_outputs",
        return_value="",
    )

    mocked_project_calls["_update_project_state.update_project_node_state"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.update_project_node_state",
        autospec=True,
    )

    mocked_project_calls["_update_project_state.notify_project_node_update"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.notify_project_node_update",
        autospec=True,
    )

    mocked_project_calls["_update_project_state.notify_project_state_update"] = mocker.patch(
        "simcore_service_webserver.db_listener._service.notify_project_state_update",
        autospec=True,
    )

    return mocked_project_calls


async def _get_outbox_events_for_task(engine: AsyncEngine, task_id: int) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(outbox_events.select().where(outbox_events.c.aggregate_id == f"{task_id}"))
        return [dict(r) for r in result.mappings().all()]


@pytest.fixture(autouse=True)
async def purge_outbox_events(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[[], Awaitable[None]]]:
    """Empties the outbox queue before and after every test.

    Claims are global (any worker claims the oldest pending event), so events
    left over from a previous test (e.g. by the retry/dead-letter tests, whose
    comp_tasks rows get cascade-deleted) would otherwise leak into the next one.
    The finalizer purges automatically; a test may also call the returned
    callable to purge in the middle of a test.
    """

    async def _purge() -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(outbox_events.delete())

    await _purge()
    yield _purge
    await _purge()


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_drain_skips_failed_aggregate_and_processes_the_rest(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    mocker: MockerFixture,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Skip-and-continue: a poisoned aggregate must not stall the healthy events
    behind it. Its (kind, aggregate_id) is excluded from the rest of the drain,
    the failure is marked on the row, and the other aggregates still get projected."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    poison_task, *healthy_tasks = [
        await create_comp_task(
            project_id=f"{project.uuid}",
            node_id=faker.uuid4(),
            outputs={},
            node_class=NodeClass.COMPUTATIONAL,
        )
        for _ in range(4)
    ]
    for task in [poison_task, *healthy_tasks]:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
            )

    async def _fails_only_for_poison(_app, _conn, task_id: int, _changed_columns: frozenset[str]) -> None:
        if task_id == poison_task["task_id"]:
            msg = "poisoned aggregate"
            raise RuntimeError(msg)

    mock_process = mocker.patch(
        "simcore_service_webserver.db_listener._service._process_outbox_event",
        autospec=True,
        side_effect=_fails_only_for_poison,
    )

    # the drain must return (no hang / no infinite loop)
    await asyncio.wait_for(claim_and_process_outbox_events(client.app, sqlalchemy_async_engine), 10)

    # every healthy aggregate was projected within this same drain
    claimed_task_ids = [call.args[2] for call in mock_process.await_args_list]
    for task in healthy_tasks:
        assert task["task_id"] in claimed_task_ids, "healthy aggregate must be projected in the same drain"

    # the healthy events are gone; the poisoned one is kept and marked for backoff
    for task in healthy_tasks:
        assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []
    poison_rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, poison_task["task_id"])
    assert len(poison_rows) == 1
    assert "poisoned aggregate" in poison_rows[0]["last_error"]


@pytest.mark.parametrize(
    "infra_error",
    [
        pytest.param(TimeoutError("infrastructure is down"), id="builtin-timeout"),
        # pool checkout starvation: sqlalchemy.exc.TimeoutError subclasses neither the
        # builtin TimeoutError nor DBAPIError, so it must be classified explicitly
        pytest.param(
            sa_exc.TimeoutError("QueuePool limit of size exceeded, connection timed out", None, None),
            id="sqlalchemy-pool-timeout",
        ),
        # e.g. the pool lost its connections after a database restart
        pytest.param(
            sa_exc.DisconnectionError("connection already closed"),
            id="sqlalchemy-disconnection",
        ),
    ],
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_drain_aborts_after_too_many_failing_aggregates(
    sqlalchemy_async_engine: AsyncEngine,
    mocker: MockerFixture,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
    infra_error: Exception,
):
    """When *every* aggregate fails with an infrastructure-like error (broken
    DB/socketio, not one bad event), the drain must stop after
    _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN distinct aggregates and leave the rest of the
    queue untouched for the next cycle.

    Infra-like classification must cover the SQLAlchemy pool exceptions too: a pool
    checkout timeout (sqlalchemy.exc.TimeoutError) is *not* a builtin TimeoutError nor a
    DBAPIError, and must still abort the drain instead of walking the whole backlog.
    """
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    tasks = [
        await create_comp_task(
            project_id=f"{project.uuid}",
            node_id=faker.uuid4(),
            outputs={},
            node_class=NodeClass.COMPUTATIONAL,
        )
        for _ in range(_MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN + 1)
    ]
    for task in tasks:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
            )

    mocker.patch(
        "simcore_service_webserver.db_listener._service._process_outbox_event",
        autospec=True,
        side_effect=infra_error,
    )

    await asyncio.wait_for(claim_and_process_outbox_events(client.app, sqlalchemy_async_engine), 10)

    # exactly one event per aggregate was marked, oldest-first, and the drain stopped:
    # the remaining event(s) keep attempts == 0
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(outbox_events.select().order_by(outbox_events.c.id))
        rows = result.mappings().all()
    assert len(rows) == len(tasks)
    attempts = [row["attempts"] for row in rows]
    assert attempts == [1] * _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN + [0]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_drain_does_not_abort_on_application_level_failures(
    sqlalchemy_async_engine: AsyncEngine,
    mocker: MockerFixture,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Application-level failures (e.g. a bug tied to specific rows) must never
    trigger the infra-outage heuristic: even with more distinct failing aggregates
    than _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN, the drain must attempt every one of them
    instead of giving up early on the healthy backlog."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    tasks = [
        await create_comp_task(
            project_id=f"{project.uuid}",
            node_id=faker.uuid4(),
            outputs={},
            node_class=NodeClass.COMPUTATIONAL,
        )
        for _ in range(_MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN + 2)
    ]
    for task in tasks:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
            )

    mocker.patch(
        "simcore_service_webserver.db_listener._service._process_outbox_event",
        autospec=True,
        side_effect=RuntimeError("bug in projection code"),
    )

    await asyncio.wait_for(claim_and_process_outbox_events(client.app, sqlalchemy_async_engine), 10)

    # every aggregate was attempted exactly once, none left untouched
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(outbox_events.select().order_by(outbox_events.c.id))
        rows = result.mappings().all()
    assert len(rows) == len(tasks)
    assert [row["attempts"] for row in rows] == [1] * len(tasks)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_concurrent_claims_do_not_double_process_same_event(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Simulates two replicas racing to claim the same outbox event: only one may win."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    results = await asyncio.gather(
        _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()),
        _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()),
    )
    winners = [r for r in results if r is not None and r.success]
    assert len(winners) == 1, "exactly one concurrent claimant should have won the event"
    # the event was processed exactly once and removed
    mock_project_subsystem["update_node_outputs"].assert_called_once()
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_concurrent_claims_serialize_same_aggregate_events(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Two concurrent claims on an aggregate with *two* pending events must never
    process it twice: the per-aggregate advisory lock makes the loser return None
    while the winner's transaction is open, and the winner's co-claim (row locks on
    the whole burst, taken only after the advisory lock was won) drains every event
    in a single projection.

    Processing is slowed down on purpose so both claimants are genuinely
    in-flight at the same time: without that, two fast, non-overlapping
    claims would legitimately both succeed (sequentially), which would make
    this test pass for the wrong reason.
    """
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"first": "update"}).where(comp_tasks.c.task_id == task["task_id"])
        )
        await conn.execute(
            comp_tasks.update().values(outputs={"second": "update"}).where(comp_tasks.c.task_id == task["task_id"])
        )
    rows_before = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows_before) == 2, "expected one event per update on the same aggregate"

    async def _slow_update_node_outputs(*args, **kwargs) -> str:
        await asyncio.sleep(0.3)
        return ""

    mock_project_subsystem["update_node_outputs"].side_effect = _slow_update_node_outputs

    results = await asyncio.gather(
        _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()),
        _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()),
    )
    successes = [r for r in results if r is not None and r.success]
    assert len(successes) == 1, (
        f"exactly one claimant may process the aggregate, the other must find it locked: got {results}"
    )
    assert None in results
    # the winner co-claimed and projected the whole burst exactly once, while the
    # loser was locked out of the aggregate -> nothing is left in the queue
    mock_project_subsystem["update_node_outputs"].assert_called_once()
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_concurrent_claims_process_different_aggregates_in_parallel(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Events for *different* aggregates must still be claimable concurrently:
    the advisory lock must not serialize unrelated aggregates."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    tasks = [
        await create_comp_task(
            project_id=f"{project.uuid}",
            node_id=faker.uuid4(),
            outputs={},
            node_class=NodeClass.COMPUTATIONAL,
        )
        for _ in range(2)
    ]
    async with sqlalchemy_async_engine.begin() as conn:
        for task in tasks:
            await conn.execute(
                comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
            )

    # both claims must be projecting at the same time to pass: the barrier only clears
    # once the two concurrent projections reach it, so if the advisory lock serialized
    # the aggregates the first claim would block forever and the wait_for would time out
    barrier = asyncio.Barrier(2)

    async def _rendezvous_on_projection(*args: Any, **kwargs: Any) -> str:
        await asyncio.wait_for(barrier.wait(), timeout=5.0)
        return ""

    mock_project_subsystem["update_node_outputs"].side_effect = _rendezvous_on_projection

    results = await asyncio.gather(
        _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()),
        _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()),
    )
    successes = [r for r in results if r is not None and r.success]
    assert len(successes) == 2, f"unrelated aggregates must be claimable at the same time: got {results}"
    assert {r.aggregate_id for r in successes} == {f"{t['task_id']}" for t in tasks}
    assert mock_project_subsystem["update_node_outputs"].call_count == 2
    for task in tasks:
        assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_advisory_lock_is_scoped_by_kind(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """The per-aggregate advisory lock key must include the event kind.

    Phase 1: a lock on this worker's own key (kind:aggregate_id) must still block the
    claim -> the per-aggregate serialization itself must not be weakened.
    Phase 2: a lock on the RAW aggregate_id (the pre-fix key, i.e. the namespace of any
    consumer that ignores kind) must NOT block the claim -> this worker's lock namespace
    is kind-prefixed and independent, which is the point of the fix.
    """
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )
    aggregate_id = f"{task['task_id']}"

    # a session-level lock held open on a dedicated connection (different backend than
    # the claim) conflicts with any pg_try_advisory_xact_lock on the same key

    # Phase 1: our namespaced key must serialize claims
    our_key = f"{DB_OUTBOX_KIND_COMP_TASK_SYNC}:{aggregate_id}"
    async with sqlalchemy_async_engine.connect() as blocker:
        got = (
            await blocker.execute(sa.select(func.pg_try_advisory_lock(func.hashtextextended(our_key, 0))))
        ).scalar_one()
        assert got, "blocking advisory lock must be acquirable on our namespaced key"
        assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None
        assert len(await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])) == 1
        await blocker.execute(sa.select(func.pg_advisory_unlock(func.hashtextextended(our_key, 0))))

    # Phase 2: the raw aggregate_id key (no kind) must NOT serialize our claims
    raw_key = aggregate_id
    async with sqlalchemy_async_engine.connect() as blocker:
        got = (
            await blocker.execute(sa.select(func.pg_try_advisory_lock(func.hashtextextended(raw_key, 0))))
        ).scalar_one()
        assert got, "blocking advisory lock must be acquirable on the raw aggregate-id key"
        outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
        assert outcome is not None
        assert outcome.success is True
        await blocker.execute(sa.select(func.pg_advisory_unlock(func.hashtextextended(raw_key, 0))))
    assert mock_project_subsystem["update_node_outputs"].call_count == 1
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_claim_ignores_events_of_a_foreign_kind(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """outbox_events is a shared table: claims must only pick up this worker's own
    `kind`, leaving events from other (hypothetical) producers untouched."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )
        await conn.execute(
            outbox_events.insert().values(
                kind="some_other.kind.v1",
                aggregate_type="some_other",
                aggregate_id="999999",
                changed_columns=[],
            )
        )

    assert DB_OUTBOX_KIND_COMP_TASK_SYNC != "some_other.kind.v1"

    # only the comp_task.sync.v1 event is claimed and processed
    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert outcome.success is True
    mock_project_subsystem["update_node_outputs"].assert_called_once()

    # the foreign-kind event is left untouched: nothing left to claim for us
    assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(outbox_events.select().where(outbox_events.c.aggregate_id == "999999"))
        remaining = result.mappings().all()
    assert len(remaining) == 1
    assert remaining[0]["attempts"] == 0


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_listen_notify_uses_dedicated_named_connection_and_wakes_up(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """The wake-up LISTEN connection must be a *dedicated* asyncpg connection (not a
    permanent check-out of the app's shared pool), named via
    OUTBOX_LISTENER_APPLICATION_NAME so it is identifiable in pg_stat_activity,
    and it must receive the outbox_wakeup notification when comp_tasks is updated."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )

    async with _with_outbox_wakeup_listener(client.app) as wakeup_event:
        assert not wakeup_event.is_set()

        # the dedicated connection is visible in pg_stat_activity under its own
        # application_name (this is what makes it identifiable in e.g. Adminer)
        async with sqlalchemy_async_engine.connect() as conn:
            found = (
                await conn.execute(
                    sa.text(_COUNT_LISTENER_CONNECTIONS_SQL).bindparams(pattern=f"{_OUTBOX_LISTENER_APPLICATION_NAME}%")
                )
            ).scalar_one()
        assert found >= 1, f"no pg_stat_activity entry for {_OUTBOX_LISTENER_APPLICATION_NAME!r}"

        # a comp_tasks change must wake the listener through the dedicated connection
        async with sqlalchemy_async_engine.begin() as write_conn:
            await write_conn.execute(
                comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
            )

        await asyncio.wait_for(wakeup_event.wait(), timeout=5.0)
        assert wakeup_event.is_set()

    # after the context manager exits, the dedicated connection is closed again
    async with sqlalchemy_async_engine.connect() as conn:
        found = (
            await conn.execute(
                sa.text(_COUNT_LISTENER_CONNECTIONS_SQL).bindparams(pattern=f"{_OUTBOX_LISTENER_APPLICATION_NAME}%")
            )
        ).scalar_one()
    assert found == 0, "the dedicated LISTEN connection must be closed on exit"


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_locked_hot_aggregate_does_not_block_younger_healthy_aggregate(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Candidate selection must de-duplicate aggregates *in SQL* before applying the
    batch limit: a burst of events on one aggregate locked by another replica must
    not crowd a younger, healthy aggregate out of the batch (head-of-line blocking).
    """
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    hot_task, healthy_task = [
        await create_comp_task(
            project_id=f"{project.uuid}",
            node_id=faker.uuid4(),
            outputs={},
            node_class=NodeClass.COMPUTATIONAL,
        )
        for _ in range(2)
    ]

    # the hot aggregate has more pending events than the candidate batch size, so
    # pre-fix (LIMIT over raw event rows) every candidate would belong to it
    num_hot_events = MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT + 2
    backdated = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            outbox_events.insert(),
            [
                {
                    "kind": DB_OUTBOX_KIND_COMP_TASK_SYNC,
                    "aggregate_type": "comp_task",
                    "aggregate_id": f"{hot_task['task_id']}",
                    "changed_columns": ["outputs"],
                    "modified": backdated,
                }
                for _ in range(num_hot_events)
            ],
        )
        # one younger event on a different (healthy) aggregate, queued behind the burst
        await conn.execute(
            outbox_events.insert().values(
                kind=DB_OUTBOX_KIND_COMP_TASK_SYNC,
                aggregate_type="comp_task",
                aggregate_id=f"{healthy_task['task_id']}",
                changed_columns=["outputs"],
            )
        )

    hot_aggregate_id = f"{hot_task['task_id']}"
    healthy_aggregate_id = f"{healthy_task['task_id']}"

    # hold the hot aggregate's advisory lock (as another replica would)
    our_key = f"{DB_OUTBOX_KIND_COMP_TASK_SYNC}:{hot_aggregate_id}"
    async with sqlalchemy_async_engine.connect() as blocker:
        got = (
            await blocker.execute(sa.select(func.pg_try_advisory_lock(func.hashtextextended(our_key, 0))))
        ).scalar_one()
        assert got, "blocking advisory lock must be acquirable on the hot aggregate's key"

        # the claim must skip the locked hot aggregate and pick the healthy one, even
        # though its single event is older-than-nothing... i.e. strictly younger
        outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
        assert outcome is not None, "a locked hot aggregate must not block a younger healthy aggregate"
        assert outcome.success is True
        assert outcome.aggregate_id == healthy_aggregate_id

        await blocker.execute(sa.select(func.pg_advisory_unlock(func.hashtextextended(our_key, 0))))

    # only the healthy aggregate was projected; the hot aggregate's events stay queued
    assert mock_project_subsystem["update_node_outputs"].call_count == 1
    assert len(await _get_outbox_events_for_task(sqlalchemy_async_engine, hot_task["task_id"])) == num_hot_events
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, healthy_task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_backed_off_event_delays_whole_aggregate_until_due(
    sqlalchemy_async_engine: AsyncEngine,
    mock_project_subsystem: dict[str, mock.Mock],
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Backoff is gate-checked per aggregate, not per row: a *fresh* event must not
    let an aggregate jump ahead while its older event is still backing off (that would
    notify the newer state before the older one and keep burning attempts on the stale
    row). Once the older event matures, the whole backlog co-claims in one projection."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    # older event, failed once and still inside its backoff window
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"old": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )
        await conn.execute(
            outbox_events.update().values(attempts=1, next_attempt_at=sa.text("now() + interval '1 hour'"))
        )

    # newer, fresh event on the same aggregate (due immediately)
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 2

    # the fresh event alone must not wake the aggregate: the backed-off older event
    # gates it, so nothing is claimable and the backlog stays untouched
    assert await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()) is None
    mock_project_subsystem["update_node_outputs"].assert_not_called()
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 2
    assert {row["attempts"] for row in rows} == {0, 1}, "no attempts burned while backed off"

    # once the older event's backoff has matured, both events are due and co-claim in
    # a single projection (older projected first, no out-of-order notification)
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(outbox_events.update().values(next_attempt_at=sa.text("now() - interval '1 hour'")))

    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert outcome.success is True
    mock_project_subsystem["update_node_outputs"].assert_called_once()
    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_failed_claim_records_attempt_before_releasing_the_aggregate(
    sqlalchemy_async_engine: AsyncEngine,
    mocker: MockerFixture,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    """Replicas holding a stale candidate must not re-process an aggregate whose
    claim just failed: the failure is recorded (attempt + backoff) in the claim
    transaction, so the aggregate is never claimable in between."""
    assert client.app
    project = await create_project(logged_user)
    await create_pipeline(project_id=f"{project.uuid}")
    task = await create_comp_task(
        project_id=f"{project.uuid}",
        node_id=faker.uuid4(),
        outputs={},
        node_class=NodeClass.COMPUTATIONAL,
    )
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    async def _failing_projection(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0.1)
        msg = "boom"
        raise RuntimeError(msg)

    mocker.patch(
        "simcore_service_webserver.db_listener._service._process_outbox_event",
        autospec=True,
        side_effect=_failing_projection,
    )

    candidate = ClaimableAggregate(kind=DB_OUTBOX_KIND_COMP_TASK_SYNC, aggregate_id=f"{task['task_id']}")

    async def _stale_claimer(delay: float):
        await asyncio.sleep(delay)
        return await _claim_and_process_aggregate(client.app, sqlalchemy_async_engine, candidate)

    # claimers start before, during and right after the first one fails
    results = await asyncio.gather(*(_stale_claimer(i * 0.02) for i in range(12)))

    assert len([r for r in results if r is not None]) == 1
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1
    assert rows[0]["attempts"] == 1
    assert "boom" in rows[0]["last_error"]
    async with sqlalchemy_async_engine.connect() as conn:
        backoff_pending = (
            await conn.execute(sa.select(outbox_events.c.next_attempt_at > func.now()).select_from(outbox_events))
        ).scalar_one()
    assert backoff_pending
