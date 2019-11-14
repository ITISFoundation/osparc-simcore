from typing import Dict, Optional

from aiohttp import web

from .application_keys import APP_CONFIG_KEY
from .client_session import persistent_client_session


def create_safe_application(config: Optional[Dict]=None) -> web.Application:
    app = web.Application()

    # Enxures config entry
    app[APP_CONFIG_KEY] = config or {}

    # Ensures persistent client session
    # NOTE: Ensures client session context is run first,
    # then any further get_client_sesions will be correctly closed
    app.cleanup_ctx.append(persistent_client_session)

    return app
