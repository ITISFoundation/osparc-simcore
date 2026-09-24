# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

"""Outbox consumer vs. socket.io notification failures.

The DB projection is durable, but the socket.io fan-out rides on top of the
outbox claim: if the emit itself fails (e.g. the RabbitMQ-backed socket.io
manager is down), the event must NOT be deleted — it has to be retried like
any other processing failure (at-least-once UI-delivery).

A user simply disconnecting is *not* an error: emitting to a room with zero
members is a no-op that returns normally, so the event is deleted as usual.

A CancelledError raised with nobody cancelling is *also* handled: the socket.io
RabbitMQ manager forges one from aio-pika's ChannelInvalidStateError, and the
drain must survive it — while a genuine cancellation still propagates.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectAtDB
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.comp_tasks import NodeClass, comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.db_listener._service import _claim_and_process_one_outbox_event
from simcore_service_webserver.db_listener.models import ClaimOutcome
from sqlalchemy.ext.asyncio import AsyncEngine


async def _get_outbox_events_for_task(engine: AsyncEngine, task_id: int) -> list[dict]:
    async with engine.connect() as conn:
        result = await conn.execute(outbox_events.select().where(outbox_events.c.aggregate_id == f"{task_id}"))
        return [dict(r) for r in result.mappings().all()]


@pytest.fixture(autouse=True)
async def purge_outbox_events(sqlalchemy_async_engine: AsyncEngine) -> AsyncIterator[None]:
    """Claims are global, so never leak events in/out of these tests (see the
    same fixture in test_db_listener__comp_tasks_projection.py)."""

    async def _purge() -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(outbox_events.delete())

    await _purge()
    yield
    await _purge()


@pytest.fixture
def mocked_socketio_emit(mocker: MockerFixture) -> MockType:
    """Patch the socket.io server the notification path emits to, so tests control
    exactly what ``sio.emit`` does (success == emitted/disconnected-users,
    side_effect == a broken socket.io backend, e.g. RabbitMQ down)."""
    sio = mock.AsyncMock()
    mocker.patch(
        "simcore_service_webserver.socketio._messages.get_socket_server",
        return_value=sio,
    )
    return sio.emit


@pytest.fixture
async def mock_project_writes(
    mocker: MockerFixture,
) -> AsyncIterator[Callable[[dict[str, Any]], None]]:
    """Keep the real notification chain (notify_project_node_update -> socket.io emit)
    but stub the DB writes / service RPCs it wraps, and let the test provide the
    project dict the notifications are built from."""
    fake_project: dict[str, Any] = {}
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.update_project_node_outputs",
        autospec=True,
        side_effect=lambda *_args, **_kw: (fake_project, ["new"]),
    )
    mocker.patch(
        "simcore_service_webserver.projects._projects_service.post_trigger_connected_service_retrieve",
        autospec=True,
    )

    def _set_project(project: dict[str, Any]) -> None:
        fake_project.clear()
        fake_project.update(project)

    return _set_project


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_socketio_emit_failure_keeps_event_for_retry(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    mock_project_writes: Callable[[dict[str, Any]], None],
    mocked_socketio_emit: MockType,
    faker: Faker,
):
    """A socket.io backend outage (RabbitMQ down) makes ``sio.emit`` raise. The outbox
    consumer must see that failure: the event is kept (claim rolled back, attempt
    recorded) instead of being silently deleted after a projection whose UI
    notification never left the process.
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
    node_id = task["node_id"]
    mock_project_writes(
        {
            "uuid": f"{project.uuid}",
            "workbench": {
                f"{node_id}": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.2",
                    "outputs": {"new": "data"},
                }
            },
        }
    )

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    # simulate a broken socket.io backend (e.g. the RabbitMQ publish fails)
    mocked_socketio_emit.side_effect = ConnectionResetError("broker connection closed")

    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert isinstance(outcome, ClaimOutcome)
    assert outcome.success is False, "a failed socket.io fan-out must fail the processing, not look like a success"

    # the emit really was attempted...
    mocked_socketio_emit.assert_awaited()

    # ...and its failure must keep the event for a retry instead of deleting it
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1, "event whose socket.io notification failed must NOT be deleted"
    assert rows[0]["attempts"] == 1
    assert "broker connection closed" in rows[0]["last_error"]


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_socketio_emit_success_deletes_event(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    mock_project_writes: Callable[[dict[str, Any]], None],
    mocked_socketio_emit: MockType,
    faker: Faker,
):
    """Emitting to a room with no members (e.g. every user disconnected) is a
    *no-op that succeeds*: no exception, so the event is deleted normally. Strict
    error propagation must not turn absent viewers into pointless retries.
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
    node_id = task["node_id"]
    mock_project_writes(
        {
            "uuid": f"{project.uuid}",
            "workbench": {
                f"{node_id}": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.2",
                    "outputs": {"new": "data"},
                }
            },
        }
    )

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    # sio.emit returns normally (nobody in the room == fine, message dropped)
    mocked_socketio_emit.return_value = None

    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert outcome.success is True
    mocked_socketio_emit.assert_awaited()

    assert await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"]) == []


def _outbox_test_project(project: ProjectAtDB, node_id) -> dict[str, Any]:
    return {
        "uuid": f"{project.uuid}",
        "workbench": {
            f"{node_id}": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.0.2",
                "outputs": {"new": "data"},
            }
        },
    }


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_forged_cancelled_error_keeps_drain_alive(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    mock_project_writes: Callable[[dict[str, Any]], None],
    mocked_socketio_emit: MockType,
    faker: Faker,
):
    """The socket.io RabbitMQ manager forges a CancelledError from aio-pika's
    ChannelInvalidStateError (e.g. the reconnect race during a RabbitMQ restart) even
    though nothing was cancelled. Nobody requested the cancellation, so the drain must
    NOT die with it: the aggregate is reported as an infrastructure failure, the event
    stays claimable, and the claim rolls back (no attempt counted).
    SEE https://github.com/miguelgrinberg/python-socketio/commit/cd7f781c022dd1d1ec3c6695a0fd6ab3ce864fd5
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
    mock_project_writes(_outbox_test_project(project, task["node_id"]))

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    # the task running this test is NOT being cancelled -> a CancelledError from the
    # socket.io layer can only be the forged one
    mocked_socketio_emit.side_effect = asyncio.CancelledError()

    outcome = await _claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set())
    assert outcome is not None
    assert outcome.success is False, "a forged cancellation must fail the claim, not kill the caller"
    assert outcome.is_infra_error is True

    # claim rolled back: event kept and untouched (no attempt counted either)
    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1, "event interrupted by a forged cancellation must stay claimable"
    assert rows[0]["attempts"] == 0


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_genuine_cancellation_still_propagates(
    sqlalchemy_async_engine: AsyncEngine,
    client: TestClient,
    logged_user: UserInfoDict,
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    create_pipeline: Callable[..., Awaitable[dict[str, Any]]],
    create_comp_task: Callable[..., Awaitable[dict[str, Any]]],
    mock_project_writes: Callable[[dict[str, Any]], None],
    mocked_socketio_emit: MockType,
    faker: Faker,
):
    """A real cancellation (e.g. app shutdown while a notification emit is in flight)
    must keep propagating: the claim rolls back (event stays claimable for the next
    replica/cycle) and the cancellation is re-raised to the cancelling caller.
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
    mock_project_writes(_outbox_test_project(project, task["node_id"]))

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            comp_tasks.update().values(outputs={"new": "data"}).where(comp_tasks.c.task_id == task["task_id"])
        )

    emit_started: asyncio.Event = asyncio.Event()

    async def _blocked_emit(*_args, **_kwargs):
        emit_started.set()
        await asyncio.sleep(3600)  # until cancelled (simulates a stalled broker publish)

    mocked_socketio_emit.side_effect = _blocked_emit

    claim = asyncio.create_task(_claim_and_process_one_outbox_event(client.app, sqlalchemy_async_engine, set()))
    await asyncio.wait_for(emit_started.wait(), timeout=10)

    claim.cancel()  # the drain task is cancelled while the emit is in flight
    with pytest.raises(asyncio.CancelledError):
        await claim

    rows = await _get_outbox_events_for_task(sqlalchemy_async_engine, task["task_id"])
    assert len(rows) == 1, "a genuinely cancelled claim must roll back, keeping the event"
    assert rows[0]["attempts"] == 0
