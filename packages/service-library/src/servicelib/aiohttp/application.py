import asyncio
import logging

from aiohttp import web

from .application_keys import APP_CONFIG_KEY, APP_FIRE_AND_FORGET_TASKS_KEY
from .client_session import persistent_client_session

_logger = logging.getLogger(__name__)


async def _first_call_on_startup(app: web.Application):
    _logger.info("Starting %s ...", f"{app}")


async def _first_call_on_shutdown(app: web.Application):
    _logger.info("Shutting down %s ...", f"{app}")


_MAX_WAIT_TIME_TO_CANCEL_SECONDS = 5


async def _cancel_all_background_tasks(app: web.Application):
    running_tasks = app[APP_FIRE_AND_FORGET_TASKS_KEY]
    task: asyncio.Task
    for task in running_tasks:
        task.cancel()
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*running_tasks, return_exceptions=True),
            timeout=_MAX_WAIT_TIME_TO_CANCEL_SECONDS,
        )
        if bad_results := list(filter(lambda r: isinstance(r, Exception), results)):
            _logger.error(
                "Following observation tasks completed with an unexpected error:%s",
                f"{bad_results}",
            )
    except asyncio.TimeoutError:
        _logger.exception(
            "Timed-out waiting more than %s secs for %s to complete. Action: Check why this is blocking",
            _MAX_WAIT_TIME_TO_CANCEL_SECONDS,
            f"{running_tasks=}",
        )


def create_safe_application(config: dict | None = None) -> web.Application:
    app = web.Application()

    # Ensures config entry
    app[APP_CONFIG_KEY] = config or {}
    app[APP_FIRE_AND_FORGET_TASKS_KEY] = set()

    app.on_startup.append(_first_call_on_startup)
    app.on_cleanup.append(_first_call_on_shutdown)

    # Ensures persistent client session
    # NOTE: Ensures client session context is run first,
    # then any further get_client_sesions will be correctly closed
    app.cleanup_ctx.append(persistent_client_session)

    # Q: Shouldn't this be THE LAST one???
    app.on_cleanup.append(_cancel_all_background_tasks)

    return app
