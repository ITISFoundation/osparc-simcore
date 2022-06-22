import asyncio
import logging
from typing import Dict, Optional

from aiohttp import web

from .application_keys import APP_CONFIG_KEY, APP_FIRE_AND_FORGET_TASKS_KEY
from .client_session import persistent_client_session

logger = logging.getLogger(__name__)


async def startup_info(app: web.Application):
    print(f"INFO: STARTING UP {app}...", flush=True)


async def shutdown_info(app: web.Application):
    print(f"INFO: SHUTTING DOWN {app} ...", flush=True)


async def stop_background_tasks(app: web.Application):
    running_tasks = app[APP_FIRE_AND_FORGET_TASKS_KEY]
    task: asyncio.Task
    for task in running_tasks:
        task.cancel()
    try:
        MAX_WAIT_TIME_SECONDS = 5
        results = await asyncio.wait_for(
            asyncio.gather(*running_tasks, return_exceptions=True),
            timeout=MAX_WAIT_TIME_SECONDS,
        )
        if bad_results := list(filter(lambda r: isinstance(r, Exception), results)):
            logger.error(
                "Following observation tasks completed with an unexpected error:%s",
                f"{bad_results}",
            )
    except asyncio.TimeoutError:
        logger.error(
            "Timed-out waiting for %s to complete. Action: Check why this is blocking",
            f"{running_tasks=}",
        )


def create_safe_application(config: Optional[Dict] = None) -> web.Application:
    app = web.Application()

    # Ensures config entry
    app[APP_CONFIG_KEY] = config or {}
    app[APP_FIRE_AND_FORGET_TASKS_KEY] = set()

    app.on_startup.append(startup_info)
    app.on_cleanup.append(shutdown_info)

    # Ensures persistent client session
    # NOTE: Ensures client session context is run first,
    # then any further get_client_sesions will be correctly closed
    app.cleanup_ctx.append(persistent_client_session)
    app.on_cleanup.append(stop_background_tasks)

    return app
