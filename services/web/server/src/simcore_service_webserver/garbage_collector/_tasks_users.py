"""
Scheduled tasks addressing users

"""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from aiohttp import web
from common_library.logging.logging_base import get_log_record_extra
from models_library.users import UserID
from servicelib.logging_utils import log_context

from ..login import login_service
from ..security import security_service
from ..users import users_service
from ._healthcheck import run_monitored_periodic_task
from ._tasks_utils import CleanupContextFunc

_logger = logging.getLogger(__name__)


async def notify_user_logout_all_sessions(app: web.Application, user_id: UserID) -> None:
    #  NOTE kept here for convenience
    with log_context(
        _logger,
        logging.INFO,
        "Forcing logout of %s from all sessions",
        f"{user_id=}",
        extra=get_log_record_extra(user_id=user_id),
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


async def _update_expired_users(app: web.Application):
    if updated := await users_service.update_expired_users(app):
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


def create_background_task_for_trial_accounts(wait_s: float) -> CleanupContextFunc:
    async def _cleanup_ctx_fun(app: web.Application) -> AsyncIterator[None]:
        interval = timedelta(seconds=wait_s)

        async with run_monitored_periodic_task(app, _update_expired_users, task_interval=interval):
            yield

    return _cleanup_ctx_fun
