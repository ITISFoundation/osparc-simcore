import logging
import re
from copy import deepcopy
from typing import Any, Final

from aiohttp import web
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientConnectionError, ClientError
from common_library.json_serialization import json_dumps
from servicelib.aiohttp.client_session import get_client_session
from tenacity.asyncio import AsyncRetrying
from tenacity.before import before_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

from .._constants import APP_PRODUCTS_KEY
from ..application_settings import ApplicationSettings, get_application_settings
from ..products.api import Product
from ._constants import (
    APP_FRONTEND_CACHED_INDEXES_KEY,
    APP_FRONTEND_CACHED_STATICS_JSON_KEY,
    FRONTEND_APPS_AVAILABLE,
)
from .settings import (
    FrontEndAppSettings,
    StaticWebserverModuleSettings,
    get_plugin_settings,
)

_RE_PRODUCTION_RELEASE_VERSION: Final[re.Pattern] = re.compile(r"^v\d+\.\d+\.\d+$")

_logger = logging.getLogger(__name__)


# This retry policy aims to overcome the inconvenient fact that the swarm
# orchestrator does not guaranteed the order in which services are started.
#
# Here the web-server needs to pull some files from the web-static service
# which might still not be ready.
#
#
_STATIC_WEBSERVER_RETRY_ON_STARTUP_POLICY: Final[dict[str, Any]] = {
    "stop": stop_after_attempt(5),
    "wait": wait_fixed(1.5),
    "before": before_log(_logger, logging.WARNING),
    "retry": retry_if_exception_type(ClientConnectionError),
    "reraise": True,
}


async def create_cached_indexes(app: web.Application) -> None:
    """
    Currently the static resources contain N folders: osparc, s4l, s4llite, s4lacad, s4lengine, tis, tiplite
    each of them contain and index.html to be served to as the root of the site
    for each type of frontend.

    Caching these 4 items on start
    """
    settings: StaticWebserverModuleSettings = get_plugin_settings(app)
    cached_indexes: dict[str, str] = {}

    session: ClientSession = get_client_session(app)

    for frontend_name in FRONTEND_APPS_AVAILABLE:
        url = URL(f"{settings.STATIC_WEBSERVER_URL}") / frontend_name
        _logger.info("Fetching index from %s", url)
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
            _logger.exception("Could not fetch index from static server")

            # ANE: Yes this is supposed to fail the boot process
            msg = f"Could not fetch index at {url!s}. Stopping application boot"
            raise RuntimeError(msg) from err

        # fixes relative paths
        body = body.replace(f"../resource/{frontend_name}", f"resource/{frontend_name}")
        body = body.replace("boot.js", f"{frontend_name}/boot.js")

        _logger.info("Storing index for %s", url)
        cached_indexes[frontend_name] = body

    app[APP_FRONTEND_CACHED_INDEXES_KEY] = cached_indexes


async def create_and_cache_statics_json(app: web.Application) -> None:
    # NOTE: in devel model, the folder might be under construction
    # (qx-compile takes time), therefore we create statics.json
    # on_startup instead of upon setup

    # Adds general server settings
    app_settings: ApplicationSettings = get_application_settings(app)
    common: dict = app_settings.to_client_statics()

    # Adds specifics to front-end app
    frontend_settings: FrontEndAppSettings | None = app_settings.WEBSERVER_FRONTEND
    if frontend_settings:
        common.update(frontend_settings.to_statics())

    # Adds products defined in db
    products: dict[str, Product] = app[APP_PRODUCTS_KEY]
    assert products  # nosec

    app[APP_FRONTEND_CACHED_STATICS_JSON_KEY] = {}
    for product in products.values():
        data = deepcopy(common)

        _logger.debug("Product %s", product.name)
        data.update(product.to_statics())

        # Adds specifics to login settings
        if (p := product.login_settings) and (v := p.get("LOGIN_2FA_REQUIRED", None)):
            data["webserverLogin"].update({"LOGIN_2FA_REQUIRED": v})

        # replace vcsReleaseUrl with curated release url
        vtag = app_settings.SIMCORE_VCS_RELEASE_TAG
        if (
            vtag
            and re.match(_RE_PRODUCTION_RELEASE_VERSION, vtag)
            and product.vendor
            and (template_url := product.vendor.get("release_notes_url_template", None))
        ):
            # template URL should be somethign like:
            # https://github.com/ITISFoundation/osparc-issues/blob/master/release-notes/osparc/{vtag}.md
            data["vcsReleaseUrl"] = template_url.format(vtag=vtag)

        data_json = json_dumps(data)
        _logger.debug("Front-end statics.json: %s", data_json)

        # cache computed statics.json
        app[APP_FRONTEND_CACHED_STATICS_JSON_KEY][product.name] = data_json
