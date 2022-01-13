""" Serves client's code

    - The client-side runs a RIA (Rich Interface Application) so the server does not
    need to render pages upon request but only serve once the code to the client.
    - The client application then interacts with the server via a http and/or socket API
    - The client application is under ``services/web/client`` and the ``webclient`` service
    is used to build it.
"""
import json
import logging
from typing import Dict

from aiohttp import web
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientConnectionError, ClientError
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.client_session import get_client_session
from tenacity import (
    AsyncRetrying,
    before_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)
from yarl import URL

from .constants import (
    APP_SETTINGS_KEY,
    INDEX_RESOURCE_NAME,
    RQ_PRODUCT_FRONTEND_KEY,
    RQ_PRODUCT_KEY,
)
from .statics_settings import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
    FrontEndAppSettings,
    StaticWebserverModuleSettings,
)

log = logging.getLogger(__name__)


STATIC_DIRNAMES = FRONTEND_APPS_AVAILABLE | {"resource", "transpiled"}

APP_FRONTEND_CACHED_INDEXES_KEY = f"{__name__}.cached_indexes"
APP_FRONTEND_CACHED_STATICS_JSON_KEY = f"{__name__}.cached_statics_json"

# NOTE: saved as a separate item to config
STATIC_WEBSERVER_SETTINGS_KEY = f"{__name__}.StaticWebserverModuleSettings"

#
# This retry policy aims to overcome the inconvenient fact that the swarm
# orchestrator does not guaranteed the order in which services are started.
#
# Here the web-server needs to pull some files from the web-static service
# which might still not be ready.
#
#
RETRY_ON_STARTUP_POLICY = dict(
    stop=stop_after_attempt(5),
    wait=wait_fixed(1.5),
    before=before_log(log, logging.WARNING),
    retry=retry_if_exception_type(ClientConnectionError),
    reraise=True,
)


def assemble_settings(app: web.Application) -> StaticWebserverModuleSettings:
    """creates stores and returns settings for this module"""
    settings = StaticWebserverModuleSettings()
    app[STATIC_WEBSERVER_SETTINGS_KEY] = settings
    return settings


def get_settings(app: web.Application) -> StaticWebserverModuleSettings:
    return app[STATIC_WEBSERVER_SETTINGS_KEY]


async def _assemble_cached_indexes(app: web.Application):
    """
    Currently the static resources are contain 3 folders: osparc, s4l, tis
    each of them contain and index.html to be served to as the root of the site
    for each type of frontend.

    Caching these 3 items on start. This
    """
    settings: StaticWebserverModuleSettings = get_settings(app)
    cached_indexes: Dict[str, str] = {}

    session: ClientSession = get_client_session(app)

    for frontend_name in FRONTEND_APPS_AVAILABLE:
        url = URL(settings.static_web_server_url) / frontend_name
        log.info("Fetching index from %s", url)

        try:
            # web-static server might still not be up
            async for attempt in AsyncRetrying(**RETRY_ON_STARTUP_POLICY):
                with attempt:
                    response = await session.get(url, raise_for_status=True)

            body = await response.text()

        except ClientError as err:
            log.error("Could not fetch index from static server: %s", err)

            # ANE: Yes this is supposed to fail the boot process
            raise RuntimeError(
                f"Could not fetch index at {str(url)}. Stopping application boot"
            ) from err

        # fixes relative paths
        body = body.replace(f"../resource/{frontend_name}", f"resource/{frontend_name}")
        body = body.replace("boot.js", f"{frontend_name}/boot.js")

        log.info("Storing index for %s", url)
        cached_indexes[frontend_name] = body

    app[APP_FRONTEND_CACHED_INDEXES_KEY] = cached_indexes


def _create_statics_settings(app) -> Dict:
    # Adds general server settings
    info: Dict = app[APP_SETTINGS_KEY].to_client_statics()

    # Adds specifics to front-end app
    info.update(FrontEndAppSettings().to_statics())

    return info


async def _assemble_statics_json(app: web.Application):
    # NOTE: in devel model, the folder might be under construction
    # (qx-compile takes time), therefore we create statics.json
    # on_startup instead of upon setup

    statics_settings: Dict = _create_statics_settings(app)

    # cache computed statics.json
    statics_json: str = json.dumps(statics_settings)
    app[APP_FRONTEND_CACHED_STATICS_JSON_KEY] = statics_json


async def get_cached_frontend_index(request: web.Request):
    log.debug("Request from host %s", request.headers["Host"])
    target_frontend = request.get(RQ_PRODUCT_FRONTEND_KEY)

    if target_frontend is None:
        log.warning("No front-end specified using default %s", FRONTEND_APP_DEFAULT)
        target_frontend = FRONTEND_APP_DEFAULT

    elif target_frontend not in FRONTEND_APPS_AVAILABLE:
        raise web.HTTPNotFound(
            reason=f"Requested front-end '{target_frontend}' is not available"
        )

    log.debug(
        "Serving front-end %s for product %s",
        request.get(RQ_PRODUCT_KEY),
        target_frontend,
    )

    # NOTE: CANNOT redirect , i.e.
    # raise web.HTTPFound(f"/{target_frontend}/index.html")
    # because it losses fragments and therefore it fails in study links.
    #
    # SEE services/web/server/tests/unit/isolated/test_redirections.py
    #

    cached_indexes: Dict[str, str] = request.app[APP_FRONTEND_CACHED_INDEXES_KEY]
    if target_frontend not in cached_indexes:
        raise web.HTTPNotFound()

    body = cached_indexes[target_frontend]
    return web.Response(body=body, content_type="text/html")


async def get_statics_json(request: web.Request):  # pylint: disable=unused-argument
    statics_json = request.app[APP_FRONTEND_CACHED_STATICS_JSON_KEY]
    return web.Response(body=statics_json, content_type="application/json")


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup_statics(app: web.Application) -> None:
    settings: StaticWebserverModuleSettings = assemble_settings(app)
    if not settings.enabled:
        log.warning("Static webserver module is disabled")
        return

    # serves information composed by making 3 http requests (once for each product)
    # to the index.html in each of the 3 product directories /osparc, /tis and /s4l
    app.router.add_get("/", get_cached_frontend_index, name=INDEX_RESOURCE_NAME)
    # statics.json is computed here and contains information used
    # by the frontend to properly render the client
    app.router.add_get("/static-frontend-data.json", get_statics_json)

    # compute statics.json content
    app.on_startup.append(_assemble_statics_json)
    # fetch all index.html for various frontends
    app.on_startup.append(_assemble_cached_indexes)
