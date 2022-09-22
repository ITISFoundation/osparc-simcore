import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator, Callable

from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy
from models_library.basic_types import IdInt
from servicelib.logging_utils import log_context
from simcore_postgres_database.models.users import UserStatus, users
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ._constants import APP_DB_ENGINE_KEY
from .login.utils import notify_user_logout
from .security_api import clean_auth_policy_cache

logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]

_SEC = 1

_PERIODIC_TASK_NAME = f"{__name__}.update_expired_users_periodically"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


async def update_expired_users(engine: Engine) -> list[IdInt]:
    now = datetime.utcnow()
    async with engine.acquire() as conn:
        result: ResultProxy = await conn.execute(
            users.update()
            .values(status=UserStatus.EXPIRED)
            .where(
                (users.c.expires_at != None)
                & (users.c.status == UserStatus.ACTIVE)
                & (users.c.expires_at < now)
            )
            .returning(users.c.id)
        )
        expired = [r.id for r in await result.fetchall()]
        return expired


@retry(
    wait=wait_exponential(min=5 * _SEC),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _update_expired_users_periodically(app: web.Application, wait_s: float):
    """Periodically check expiration dates and updates user status

    It is resilient, i.e. if update goes wrong, it waits a bit and retries
    """
    engine: Engine = app[APP_DB_ENGINE_KEY]
    assert engine  # nosec

    while True:
        if updated := await update_expired_users(engine):
            # expired users might be cached in the auth. If so, any request
            # with this user-id will get thru producing unexpected side-effects
            clean_auth_policy_cache(app)

            # broadcast force logout of user_id
            for user_id in updated:
                logger.info("User account with %s expired", f"{user_id=}")

                with log_context(
                    logger,
                    logging.INFO,
                    "Forcing logout of %s from all sessions",
                    f"{user_id=}",
                ):
                    await notify_user_logout(app, user_id, client_session_id=None)

        else:
            logger.info("No users expired")

        await asyncio.sleep(wait_s)


def create_background_task_for_trial_accounts(
    wait_s: float, task_name: str = _PERIODIC_TASK_NAME
) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(
        app: web.Application,
    ) -> AsyncIterator[None]:

        # setup
        task = asyncio.create_task(
            _update_expired_users_periodically(app, wait_s),
            name=task_name,
        )
        app[_APP_TASK_KEY] = task

        yield

        # tear-down
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            assert task.cancelled()  # nosec

    return _cleanup_ctx_fun
