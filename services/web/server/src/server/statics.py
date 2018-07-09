"""

"""
import os
import logging
from functools import partial

from aiohttp import web

_LOGGER = logging.getLogger(__file__)


async def index(client_dir, request):
    """
        Serves boot application
    """
    _LOGGER.debug("index.request:\n %s", request)

    index_path = os.path.join(client_dir, "index.html")
    with open(index_path) as ofh:
        return web.Response(text=ofh.read(), content_type="text/html")


def setup_statics(app):
    _LOGGER.debug("Setting up ... ")

    client_dir = app["config"]["SIMCORE_CLIENT_OUTDIR"]

    # RIA qx-application
    app.router.add_get("/", partial(index, client_dir=client_dir))

    # TODO: check whether this can be done at once
    app.router.add_static("/qxapp", os.path.join(client_dir, "qxapp"))
    app.router.add_static("/transpiled", os.path.join(client_dir, "transpiled"))
    app.router.add_static("/resource", os.path.join(client_dir, "resource"))
