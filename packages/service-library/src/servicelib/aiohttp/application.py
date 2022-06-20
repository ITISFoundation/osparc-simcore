import asyncio
from typing import Dict, Optional

from aiohttp import web

from .application_keys import APP_CONFIG_KEY, APP_FIRE_AND_FORGET_TASKS_KEY
from .client_session import persistent_client_session


async def startup_info(app: web.Application):
    print(f"INFO: STARTING UP {app}...", flush=True)


async def shutdown_info(app: web.Application):
    print(f"INFO: SHUTTING DOWN {app} ...", flush=True)


async def stop_background_tasks(app: web.Application):
    task: asyncio.Task
    for task in app[APP_FIRE_AND_FORGET_TASKS_KEY]:
        task.cancel()
    await asyncio.gather(*(app[APP_FIRE_AND_FORGET_TASKS_KEY]), return_exceptions=True)


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
