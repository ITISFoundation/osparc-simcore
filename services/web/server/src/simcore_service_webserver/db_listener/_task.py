"""Background-task lifecycle of the db_listener domain.

Wires the outbox drain (`_service.claim_and_process_outbox_events`) into the app's
cleanup_ctx as a periodic task, plus a dedicated LISTEN connection on the outbox
wake-up channel so a pg_notify drains the outbox immediately instead of waiting for
the next poll interval. Losing this connection only loses wake-ups — the table
remains the source of truth and the periodic poll picks up anything missed.
"""

import asyncio
import contextlib
import datetime
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Final

import asyncpg
import asyncpg.pool
from aiohttp import web
from servicelib.background_task import periodic_task
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME

from .._meta import APP_NAME
from ..db.plugin import get_asyncpg_engine
from ..db.settings import get_plugin_settings
from ._service import claim_and_process_outbox_events

_OUTBOX_POLL_INTERVAL_S: Final[int] = 30

# shown as pg_stat_activity.application_name for the dedicated LISTEN connection,
# so it can be told apart from the app's pooled connections in e.g. Adminer
OUTBOX_LISTENER_APPLICATION_NAME: Final[str] = f"{APP_NAME}-db-listener-outbox"

_logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def with_outbox_wakeup_listener(
    app: web.Application,
) -> AsyncGenerator[asyncio.Event]:
    """Holds one dedicated connection open to LISTEN on the outbox wake-up channel.

    The connection is opened directly with asyncpg, *outside* the app's shared
    SQLAlchemy pool: asyncpg's callback-based notifications require holding one
    connection open for the listener's lifetime, and a permanent check-out from
    the shared pool would steal capacity from request-handling code (projections
    also need pool connections while the LISTEN one is held).
    It is therefore named via `OUTBOX_LISTENER_APPLICATION_NAME` so it is easy to
    identify in pg_stat_activity (e.g. in the Adminer dashboard).

    Yields the event that pg_notify('outbox_wakeup') sets: pass it as the
    `early_wake_up_event` of a periodic drain task, so events are picked up as
    soon as they land instead of waiting for the next poll interval.
    """
    settings = get_plugin_settings(app)
    wakeup_event: asyncio.Event = asyncio.Event()

    def _on_wakeup(
        _conn: asyncpg.Connection | asyncpg.pool.PoolConnectionProxy,
        _pid: int,
        _channel: str,
        _payload: object,
    ) -> None:
        wakeup_event.set()

    listen_conn = await asyncpg.connect(
        dsn=settings.dsn,
        server_settings={
            "jit": "off",  # same as the app's pooled engine connections
            "application_name": settings.client_name(OUTBOX_LISTENER_APPLICATION_NAME, suffix="asyncpg"),
        },
    )
    try:
        await listen_conn.add_listener(DB_CHANNEL_NAME, _on_wakeup)
        try:
            yield wakeup_event
        finally:
            await listen_conn.remove_listener(DB_CHANNEL_NAME, _on_wakeup)
    finally:
        await listen_conn.close()


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    # the dedicated LISTEN connection stays open for the task's lifetime (outside
    # the shared pool) and a pg_notify wake-up drains the outbox immediately,
    # instead of waiting for the poll interval
    async with (
        with_outbox_wakeup_listener(app) as wakeup_event,
        periodic_task(
            claim_and_process_outbox_events,
            interval=datetime.timedelta(seconds=_OUTBOX_POLL_INTERVAL_S),
            task_name="outbox projector",
            early_wake_up_event=wakeup_event,
            app=app,
            engine=get_asyncpg_engine(app),
        ),
    ):
        yield
