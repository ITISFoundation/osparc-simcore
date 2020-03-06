from typing import Dict, Optional

from aiohttp import web

from .application_keys import APP_CONFIG_KEY
from .client_session import persistent_client_session

async def startup_info(app: web.Application):
    print(f"INFO: STARTING UP {app}...", flush=True)


async def shutdown_info(app: web.Application):
    print(f"INFO: SHUTING DOWN {app} ...", flush=True)


def create_safe_application(config: Optional[Dict]=None) -> web.Application:
    app = web.Application()

    # Enxures config entry
    app[APP_CONFIG_KEY] = config or {}

    app.on_startup.append(startup_info)
    app.on_cleanup.append(shutdown_info)

    # Ensures persistent client session
    # NOTE: Ensures client session context is run first,
    # then any further get_client_sesions will be correctly closed
    app.cleanup_ctx.append(persistent_client_session)

    return app
