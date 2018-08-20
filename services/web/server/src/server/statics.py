""" Serves client's code

    - The client-side runs a RIA (Rich Interface Application) so the server does not
    need to render pages upon request but only serve once the code to the client.
    - The client application then interacts with the server via a http and/or socket API
    - The client application is under ``services/web/client`` and the ``webclient`` service
    is used to build it.
"""
import os
import logging

from aiohttp import web

_LOGGER = logging.getLogger(__file__)


async def index(request):
    """
        Serves boot application under index
    """
    _LOGGER.debug("index.request:\n %s", request)

    client_dir = request.app["config"]["SIMCORE_CLIENT_OUTDIR"]
    index_path = os.path.join(client_dir, "index.html")
    with open(index_path) as ofh:
        return web.Response(text=ofh.read(), content_type="text/html")


def setup_statics(app):
    _LOGGER.debug("Setting up %s ...", __name__)

    outdir = app["config"]["SIMCORE_CLIENT_OUTDIR"]

    if not os.path.exists(outdir):
        # FIXME: This error is silent to let tests pass
        _LOGGER.error("Client application is not ready. Invalid path %s", outdir)
        return

    # RIA qx-application
    app.router.add_get("/", index)

    # TODO: check whether this can be done at once
    # NOTE: source-output and build-output have both the same subfolder structure
    for name in ("qxapp", "transpiled", "resource"):
        folderpath = os.path.join(outdir, name)
        if os.path.exists(folderpath):
            app.router.add_static('/' + name, folderpath)
        else:
            _LOGGER.error("Missing client folder %s", folderpath)
