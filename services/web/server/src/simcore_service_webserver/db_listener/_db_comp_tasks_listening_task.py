"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.

This is a thin PG -> RabbitMQ relay: on notification it resolves the project
owner and republishes a `NodeDataUpdatedEventMessage` event (no embedded values).
Actual handling (re-reading comp_tasks and notifying the project) happens in
the RabbitMQ consumer (see notifications/_rabbitmq_exclusive_queue_consumers.py),
which runs on every (already horizontally-scaled) webserver-api replica.

The LISTEN loop itself is guarded by a Redis exclusive lock (see
`create_comp_tasks_listening_task`) so it can run safely as a plain background
task on every webserver-api replica too - no dedicated singleton service needed.
"""

import asyncio
import datetime
import logging
from collections.abc import AsyncIterator
from typing import Final, Literal, NoReturn

import asyncpg
from aiohttp import web
from common_library.async_tools import cancel_wait_task
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import NodeDataUpdatedEventMessage
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.background_task_utils import exclusive_periodic
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from ..db.settings import get_plugin_settings
from ..projects import exceptions
from ..rabbitmq import get_rabbitmq_client
from ..redis import get_redis_lock_manager_client_sdk
from ._models import CompTaskNotificationPayload

_LISTENING_TASK_BASE_SLEEPING_TIME_S: Final[int] = 1
_logger = logging.getLogger(__name__)


async def _get_project_owner(conn: AsyncConnection, project_uuid: ProjectID) -> UserID:
    the_project_owner: PositiveInt | None = (
        await conn.execute(select(projects.c.prj_owner).where(projects.c.uuid == f"{project_uuid}"))
    ).scalar_one_or_none()
    if not the_project_owner:
        raise exceptions.ProjectOwnerNotFoundError(project_uuid=project_uuid)
    return UserID(the_project_owner)


async def _handle_db_notification(
    app: web.Application, payload: CompTaskNotificationPayload, engine: AsyncEngine
) -> None:
    changes: list[Literal["outputs", "state"]] = []
    if any(field in payload.changes for field in ("outputs", "run_hash")):
        changes.append("outputs")
    if "state" in payload.changes:
        changes.append("state")
    if not changes:
        return

    try:
        async with engine.connect() as conn:
            the_project_owner = await _get_project_owner(conn, payload.project_id)

        message = NodeDataUpdatedEventMessage(
            user_id=the_project_owner,
            project_id=payload.project_id,
            node_id=payload.node_id,
            changes=changes,
        )
        await get_rabbitmq_client(app).publish(message.channel_name, message)

    except exceptions.ProjectOwnerNotFoundError as exc:
        _logger.warning(
            "Project owner of project %s could not be found, is the project valid?",
            exc.project_uuid,
        )


async def _listen(app: web.Application) -> NoReturn:
    engine = get_asyncpg_engine(app)
    settings = get_plugin_settings(app)

    # Use a dedicated raw asyncpg connection for LISTEN/NOTIFY.
    # SQLAlchemy's connection wrapper does not support asyncpg's callback-based
    # notification delivery, so we create a standalone asyncpg connection.
    notifications: asyncio.Queue[str] = asyncio.Queue()

    def _on_notification(
        _conn: object,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        notifications.put_nowait(payload)

    asyncpg_conn = await asyncpg.connect(dsn=settings.dsn)
    try:
        # Use asyncpg's native connection.add_listener(channel, callback) for event-driven notifications
        # (replaces polling — more efficient)
        await asyncpg_conn.add_listener(DB_CHANNEL_NAME, _on_notification)  # type: ignore[arg-type]
        try:
            while True:
                try:
                    raw_payload = await asyncio.wait_for(
                        notifications.get(),
                        timeout=_LISTENING_TASK_BASE_SLEEPING_TIME_S,
                    )
                except TimeoutError:
                    if asyncpg_conn.is_closed():
                        msg = "connection with database is closed!"
                        raise ConnectionError(msg) from None
                    continue

                payload = CompTaskNotificationPayload.model_validate_json(raw_payload)
                _logger.debug("received update from database: %s", f"{payload=}")
                await _handle_db_notification(app, payload, engine)
        finally:
            if not asyncpg_conn.is_closed():
                await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_notification)  # type: ignore[arg-type]
    finally:
        if not asyncpg_conn.is_closed():
            await asyncpg_conn.close()


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    # NOTE: this task is safe to run on every webserver-api replica (no dedicated
    # singleton `wb-db-event-listener` service needed): the Redis lock below ensures
    # only one replica actually holds the LISTEN connection at a time, with automatic
    # failover to another replica if that one goes down.
    @exclusive_periodic(
        get_redis_lock_manager_client_sdk(app),
        task_interval=datetime.timedelta(seconds=_LISTENING_TASK_BASE_SLEEPING_TIME_S),
        retry_after=datetime.timedelta(seconds=_LISTENING_TASK_BASE_SLEEPING_TIME_S),
    )
    async def _exclusive_listen() -> None:
        await _listen(app)

    task = asyncio.create_task(_exclusive_listen(), name="computation db listener")
    try:
        yield
    finally:
        await cancel_wait_task(task)
