"""
Scheduled tasks addressing users

"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable

from aiohttp import web
from common_library.async_tools import cancel_and_shielded_wait
from models_library.users import UserID
from servicelib.logging_utils import get_log_record_extra, log_context
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_exponential

from ..login import login_service
from ..security import security_service
from ..users.api import update_expired_users

_logger = logging.getLogger(__name__)

CleanupContextFunc = Callable[[web.Application], AsyncIterator[None]]


_PERIODIC_TASK_NAME = f"{__name__}.update_expired_users_periodically"
_APP_TASK_KEY = f"{_PERIODIC_TASK_NAME}.task"


async def notify_user_logout_all_sessions(
    app: web.Application, user_id: UserID
) -> None:
    #  NOTE kept here for convenience
    with log_context(
        _logger,
        logging.INFO,
        "Forcing logout of %s from all sessions",
        f"{user_id=}",
        get_log_record_extra(user_id=user_id),
    ):
        try:
            await login_service.notify_user_logout(app, user_id, client_session_id=None)
        except Exception:  # pylint: disable=broad-except
            _logger.warning(
                "Ignored error while notifying logout for %s",
                f"{user_id=}",
                exc_info=True,
                extra=get_log_record_extra(user_id=user_id),
            )


@retry(
    wait=wait_exponential(min=5, max=20),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
    # NOTE: this function does suppresses all exceptions and retry indefinitly
)
async def _update_expired_users(app: web.Application):
    """
    It is resilient, i.e. if update goes wrong, it waits a bit and retries
    """

    if updated := await update_expired_users(app):
        # expired users might be cached in the auth. If so, any request
        # with this user-id will get thru producing unexpected side-effects
        await security_service.clean_auth_policy_cache(app)

        # broadcast force logout of user_id
        for user_id in updated:
            _logger.info(
                "User account with %s expired",
                f"{user_id=}",
                extra=get_log_record_extra(user_id=user_id),
            )

            # NOTE: : this notification will never reach sockets because it runs in the GC!!
            # We need a mechanism to send messages from GC to the webservers
            # OR a way to notify from the database changes back to the web-servers (similar to compuational services)
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3387

    else:
        _logger.info("No users expired")


async def _update_expired_users_periodically(
    app: web.Application, wait_interval_s: float
):
    """Periodically checks expiration dates and updates user status"""

    while True:
        await _update_expired_users(app)
        await asyncio.sleep(wait_interval_s)


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
        await cancel_and_shielded_wait(task)

    return _cleanup_ctx_fun
