import asyncio
import logging

from aiohttp import web

from .application_keys import APP_CONFIG_KEY, APP_FIRE_AND_FORGET_TASKS_KEY
from .client_session import persistent_client_session

_logger = logging.getLogger(__name__)


async def _first_call_on_startup(app: web.Application):
    # NOTE: name used in tests to mocker.spy
    _logger.info("Starting %s ...", f"{app}")


async def _first_call_on_cleanup(app: web.Application):
    # NOTE: name used in tests to mocker.spy
    _logger.info("Shutdown completed. Cleaning up %s ...", f"{app}")


_MAX_WAIT_TIME_TO_CANCEL_SECONDS = 5


async def _cancel_all_fire_and_forget_registered_tasks(app: web.Application):
    registered_tasks: set[asyncio.Task] = app[APP_FIRE_AND_FORGET_TASKS_KEY]
    for task in registered_tasks:
        task.cancel()

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*registered_tasks, return_exceptions=True),
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
            f"{registered_tasks=}",
        )


def create_safe_application(config: dict | None = None) -> web.Application:
    app = web.Application()

    # Ensures config entry
    app[APP_CONFIG_KEY] = config or {}
    app[APP_FIRE_AND_FORGET_TASKS_KEY] = set()

    # Events are triggered as follows
    # SEE https://docs.aiohttp.org/en/stable/web_advanced.html#aiohttp-web-signals
    #
    #  cleanup_ctx[0].setup   ---> begin of cleanup_ctx
    #  cleanup_ctx[1].setup.
    #      ...
    #  on_startup[0].
    #  on_startup[1].
    #      ...
    #  on_shutdown[0].
    #  on_shutdown[1].
    #      ...
    #  cleanup_ctx[1].teardown.
    #  cleanup_ctx[0].teardown <--- end of cleanup_ctx
    #  on_cleanup[0].
    #  on_cleanup[1].
    #      ...
    #
    app.on_startup.append(_first_call_on_startup)

    # NOTE: Ensures client session context is run first (setup),
    # then any further get_client_sesions will be correctly closed
    app.cleanup_ctx.append(persistent_client_session)

    app.on_cleanup.append(_first_call_on_cleanup)
    app.on_cleanup.append(_cancel_all_fire_and_forget_registered_tasks)

    return app
