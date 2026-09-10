# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import (
    DB_CHANNEL_NAME,
    NodeClass,
    comp_tasks,
)
from simcore_postgres_database.models.outbox_events import outbox_events
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql.elements import literal_column


@pytest.fixture()
async def db_connection(asyncpg_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with asyncpg_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        yield conn


@pytest.fixture()
async def db_notification_queue(
    db_connection: AsyncConnection,
) -> AsyncIterator[asyncio.Queue]:
    notifications_queue: asyncio.Queue = asyncio.Queue()

    raw_conn = await db_connection.get_raw_connection()
    driver_conn = raw_conn.driver_connection

    def _on_notification(_connection, _pid, _channel, payload):
        notifications_queue.put_nowait(payload)

    await driver_conn.add_listener(DB_CHANNEL_NAME, _on_notification)
    assert notifications_queue.empty()
    yield notifications_queue

    assert notifications_queue.empty(), (
        f"the notification queue was not emptied: {notifications_queue.qsize()} remaining notifications"
    )
    await driver_conn.remove_listener(DB_CHANNEL_NAME, _on_notification)


@pytest.fixture()
async def task(
    db_connection: AsyncConnection,
    db_notification_queue: asyncio.Queue,
    task_class: NodeClass,
) -> dict:
    result = await db_connection.execute(
        comp_tasks.insert().values(outputs=json.dumps({}), node_class=task_class).returning(literal_column("*"))
    )
    row = result.mappings().one()
    assert row
    task = dict(row)

    assert db_notification_queue.empty(), "database triggered change although it should only trigger on updates!"

    return task


async def _assert_wakeup_notifications(notification_queue: asyncio.Queue, num_exp_messages: int) -> None:
    """the outbox_wakeup channel only carries an empty payload: it's just a wake-up ping"""
    if num_exp_messages > 0:
        assert not notification_queue.empty()

    for _ in range(num_exp_messages):
        msg = await asyncio.wait_for(notification_queue.get(), timeout=5)
        assert msg == "", f"outbox_wakeup notification payload must be empty, got {msg!r}"
    assert notification_queue.empty(), f"there are {notification_queue.qsize()} remaining messages in the queue"


async def _assert_outbox_events_for_task(conn: AsyncConnection, task_id: int, num_exp_events: int) -> list[dict]:
    result = await conn.execute(
        outbox_events.select().where(outbox_events.c.aggregate_id == f"{task_id}").order_by(outbox_events.c.id)
    )
    rows = [dict(r) for r in result.mappings().all()]
    assert len(rows) == num_exp_events, f"expected {num_exp_events} outbox events for task {task_id}, got {rows}"
    for row in rows:
        assert row["kind"] == "comp_task.sync.v1"
        assert row["aggregate_type"] == "comp_task"
        assert row["aggregate_id"] == f"{task_id}"
    return rows


async def _update_comp_task_with(conn: AsyncConnection, task: dict, **kwargs):
    await conn.execute(comp_tasks.update().values(**kwargs).where(comp_tasks.c.task_id == task["task_id"]))


@pytest.mark.parametrize(
    "task_class",
    [(NodeClass.COMPUTATIONAL), (NodeClass.INTERACTIVE), (NodeClass.FRONTEND)],
)
async def test_listen_query(
    db_notification_queue: asyncio.Queue,
    db_connection: AsyncConnection,
    task: dict,
):
    """this tests how the postgres LISTEN query and in particular the asyncpg implementation of it works"""
    task_id = task["task_id"]

    # let's test the trigger
    updated_output = {"some new stuff": "it is new"}
    await _update_comp_task_with(db_connection, task, outputs=updated_output, state=StateType.ABORTED)
    await _assert_wakeup_notifications(db_notification_queue, 1)
    await _assert_outbox_events_for_task(db_connection, task_id, 1)
    await db_connection.execute(outbox_events.delete().where(outbox_events.c.aggregate_id == f"{task_id}"))

    # setting the exact same data twice triggers only ONCE
    updated_output = {"some new stuff": "it is newer"}
    await _update_comp_task_with(db_connection, task, outputs=updated_output)
    await _update_comp_task_with(db_connection, task, outputs=updated_output)
    await _assert_wakeup_notifications(db_notification_queue, 1)
    await _assert_outbox_events_for_task(db_connection, task_id, 1)
    await db_connection.execute(outbox_events.delete().where(outbox_events.c.aggregate_id == f"{task_id}"))

    # updating a number of times with different stuff comes out in FIFO order (one outbox event per update)
    NUM_CALLS = 20
    for n in range(NUM_CALLS):
        new_output = {"some new stuff": f"a {n} time"}
        await _update_comp_task_with(db_connection, task, outputs=new_output)

    await _assert_wakeup_notifications(db_notification_queue, NUM_CALLS)
    await _assert_outbox_events_for_task(db_connection, task_id, NUM_CALLS)
