import asyncio
import logging
from datetime import datetime

from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from simcore_postgres_database.models.users import UserStatus, users
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ._constants import APP_DB_ENGINE_KEY

logger = logging.getLogger(__name__)


_SEC = 1
_MINUTE = 60 * _SEC
_HOUR = 60 * _MINUTE
_DAY = 24 * _HOUR


_PERIODIC_TASK_NAME = f"{__name__}.update_expired_users_periodically"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


async def update_expired_users(engine: Engine) -> list[IdInt]:
    now = datetime.utcnow()
    async with engine.acquire() as conn:
        result: ResultProxy = await conn.execute(
            users.update()
            .values(status=UserStatus.EXPIRED)
            .where(
                (users.c.status == UserStatus.ACTIVE)
                & (users.c.expires_at != None)
                & (users.c.expires_at > now)
            )
            .returning(users.c.id)
        )
    updated_userids: list[IdInt] = await result.fetchall()
    return updated_userids


@retry(
    wait=wait_exponential(min=5 * _SEC),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _update_expired_users_periodically(
    engine: Engine, repeat: float = 0.5 * _DAY
):
    """Periodically check expiration dates and updates user status

    It is resilient, i.e. if update goes wrong, it waits a bit and retries
    """
    while True:
        updated = await update_expired_users(engine)
        if updated:
            for user_id in updated:
                logger.info("User account with %s expired", f"{user_id=}")

        asyncio.sleep(repeat)


async def run_bg_task_to_monitor_expiration_trial_accounts(
    app: web.Application,
):
    engine: Engine = app[APP_DB_ENGINE_KEY]
    assert engine  # nosec

    # setup
    task = asyncio.create_task(
        _update_expired_users_periodically(
            engine,
        ),
        name=_PERIODIC_TASK_NAME,
    )
    app[_APP_TASK_KEY] = task

    yield

    # tear-down
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        assert task.cancelled()  # nosec
