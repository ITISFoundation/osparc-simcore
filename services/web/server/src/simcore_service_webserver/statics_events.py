import logging
from typing import Dict

from aiohttp import web
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientConnectionError, ClientError
from servicelib.aiohttp.client_session import get_client_session
from servicelib.json_serialization import json_dumps
from tenacity._asyncio import AsyncRetrying
from tenacity.before import before_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

from ._constants import APP_SETTINGS_KEY
from .statics_constants import (
    APP_FRONTEND_CACHED_INDEXES_KEY,
    APP_FRONTEND_CACHED_STATICS_JSON_KEY,
    FRONTEND_APPS_AVAILABLE,
)
from .statics_settings import (
    FrontEndAppSettings,
    StaticWebserverModuleSettings,
    get_plugin_settings,
)

log = logging.getLogger(__name__)


# This retry policy aims to overcome the inconvenient fact that the swarm
# orchestrator does not guaranteed the order in which services are started.
#
# Here the web-server needs to pull some files from the web-static service
# which might still not be ready.
#
#
_STATIC_WEBSERVER_RETRY_ON_STARTUP_POLICY = dict(
    stop=stop_after_attempt(5),
    wait=wait_fixed(1.5),
    before=before_log(log, logging.WARNING),
    retry=retry_if_exception_type(ClientConnectionError),
    reraise=True,
)


async def assemble_cached_indexes(app: web.Application):
    """
    Currently the static resources are contain 3 folders: osparc, s4l, tis
    each of them contain and index.html to be served to as the root of the site
    for each type of frontend.

    Caching these 3 items on start. This
    """
    settings: StaticWebserverModuleSettings = get_plugin_settings(app)
    cached_indexes: Dict[str, str] = {}

    session: ClientSession = get_client_session(app)

    for frontend_name in FRONTEND_APPS_AVAILABLE:
        url = URL(settings.STATIC_WEBSERVER_URL) / frontend_name
        log.info("Fetching index from %s", url)
        try:
            body = ""
            # web-static server might still not be up
            async for attempt in AsyncRetrying(
                **_STATIC_WEBSERVER_RETRY_ON_STARTUP_POLICY
            ):
                with attempt:
                    response = await session.get(url, raise_for_status=True)
                    body = await response.text()

        except ClientError as err:
            log.error("Could not fetch index from static server: %s", err)

            # ANE: Yes this is supposed to fail the boot process
            raise RuntimeError(
                f"Could not fetch index at {str(url)}. Stopping application boot"
            ) from err
        else:
            # fixes relative paths
            body = body.replace(
                f"../resource/{frontend_name}", f"resource/{frontend_name}"
            )
            body = body.replace("boot.js", f"{frontend_name}/boot.js")

            log.info("Storing index for %s", url)
            cached_indexes[frontend_name] = body

    app[APP_FRONTEND_CACHED_INDEXES_KEY] = cached_indexes


async def assemble_statics_json(app: web.Application):
    # NOTE: in devel model, the folder might be under construction
    # (qx-compile takes time), therefore we create statics.json
    # on_startup instead of upon setup

    # Adds general server settings
    app_settings = app[APP_SETTINGS_KEY]
    info: Dict = app_settings.to_client_statics()

    # Adds specifics to front-end app
    frontend_settings: FrontEndAppSettings = app_settings.WEBSERVER_FRONTEND
    info.update(frontend_settings.to_statics())

    # cache computed statics.json
    app[APP_FRONTEND_CACHED_STATICS_JSON_KEY] = json_dumps(info)
