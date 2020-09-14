import logging
import re
from typing import Optional

from aiohttp import web

from servicelib.application_setup import ModuleCategory, app_module_setup

from .__version__ import api_vtag
from .constants import RQ_PRODUCT_KEY

log = logging.getLogger(__name__)

FE_APPS = [
    "osparc",
    #"s4l",
    #"tis",
]  # TODO: <--- This is defined by services/web/client/compile.json

DEFAULT_FE_APP = FE_APPS[0]
PRODUCT_PATH_RE = re.compile(r"^/(" + "|".join(FE_APPS) + r")/index.html")


def discover_product_by_hostname(request: web.Request) -> Optional[str]:
    # TODO: improve!!! Access to db once??
    for fea in FE_APPS:
        if fea in request.host:
            log.debug("%s discovered", fea)
            return fea
    log.debug("Could not discover FE app")
    return None


@web.middleware
async def discover_product_middleware(request, handler):
    if request.path.startswith(f"/{api_vtag}"):  # API
        frontend_app = discover_product_by_hostname(request) or DEFAULT_FE_APP
        request[RQ_PRODUCT_KEY] = frontend_app

    else:
        # /s4/boot.js is called with 'Referer': 'http://localhost:9081/s4l/index.html'

        # if path to index, e.g. /s4l/index.html'
        match = PRODUCT_PATH_RE.match(request.path)
        if match:
            request[RQ_PRODUCT_KEY] = match.group(1)
        else:
            request[RQ_PRODUCT_KEY] = DEFAULT_FE_APP

    response = await handler(request)

    # FIXME: notice that if raised error, it will not be attached
    # if RQ_PRODUCT_NAME_KEY in request:
    #    response.headers[PRODUCT_NAME_HEADER] = request[RQ_PRODUCT_NAME_KEY]

    return response


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup_products(app: web.Application):
    app.middlewares.append(discover_product_middleware)
