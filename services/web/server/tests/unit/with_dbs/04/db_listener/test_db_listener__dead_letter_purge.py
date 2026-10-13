# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access

import datetime as dt
from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
from faker import Faker
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.webserver_models import DB_OUTBOX_KIND_COMP_TASK_SYNC
from simcore_service_webserver.db_listener._repository import EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER
from simcore_service_webserver.db_listener._service import _DEAD_LETTER_RETENTION, purge_dead_letters
from sqlalchemy.ext.asyncio import AsyncEngine

_MODIFIER_TRIGGER = "auto_update_modified_timestamp"


@pytest.fixture
async def empty_outbox(sqlalchemy_async_engine: AsyncEngine) -> AsyncIterator[None]:
    async def _purge() -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(outbox_events.delete())

    await _purge()
    yield
    await _purge()


async def _insert_event(
    engine: AsyncEngine,
    aggregate_id: str,
    *,
    attempts: int,
    modified: dt.datetime,
) -> None:
    # the auto-update trigger rewrites `modified` on every insert, so it must be
    # disabled while inserting rows with an explicit backdated `modified`
    async with engine.begin() as conn:
        await conn.execute(sa.text(f"ALTER TABLE outbox_events DISABLE TRIGGER {_MODIFIER_TRIGGER}"))
        await conn.execute(
            outbox_events.insert().values(
                kind=DB_OUTBOX_KIND_COMP_TASK_SYNC,
                aggregate_type="comp_task",
                aggregate_id=aggregate_id,
                changed_columns=["outputs"],
                attempts=attempts,
                modified=modified,
            )
        )
        await conn.execute(sa.text(f"ALTER TABLE outbox_events ENABLE TRIGGER {_MODIFIER_TRIGGER}"))


async def _count_events(engine: AsyncEngine, aggregate_id: str) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(outbox_events.select().where(outbox_events.c.aggregate_id == aggregate_id))
        return len(result.fetchall())


async def test_purge_dead_letters_removes_only_expired_dead_letters(
    sqlalchemy_async_engine: AsyncEngine,
    empty_outbox: None,
    faker: Faker,
):
    """The purge bounds dead-letter accumulation: only dead-letters older than the
    retention are removed; recent dead-letters (post-mortem) and retryable events
    are kept."""
    expired_ids: list[str] = [faker.pystr() for _ in range(2)]
    expired = dt.datetime.now(dt.UTC) - _DEAD_LETTER_RETENTION - dt.timedelta(days=1)
    for aggregate_id in expired_ids:
        await _insert_event(
            sqlalchemy_async_engine, aggregate_id, attempts=EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER, modified=expired
        )

    # dead-letter within the retention -> kept for post-mortem
    recent_aggregate_id = faker.pystr()
    await _insert_event(
        sqlalchemy_async_engine,
        recent_aggregate_id,
        attempts=EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
        modified=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
    )

    # expired but still retryable (attempts below max) -> kept
    retrying_aggregate_id = faker.pystr()
    await _insert_event(
        sqlalchemy_async_engine,
        retrying_aggregate_id,
        attempts=EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER - 1,
        modified=expired,
    )

    await purge_dead_letters(sqlalchemy_async_engine)

    for aggregate_id in expired_ids:
        assert await _count_events(sqlalchemy_async_engine, aggregate_id) == 0
    assert await _count_events(sqlalchemy_async_engine, recent_aggregate_id) == 1
    assert await _count_events(sqlalchemy_async_engine, retrying_aggregate_id) == 1
