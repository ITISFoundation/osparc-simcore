""" Serves client's code

    - The client-side runs a RIA (Rich Interface Application) so the server does not
    need to render pages upon request but only serve once the code to the client.
    - The client application then interacts with the server via a http and/or socket API
    - The client application is under ``services/web/client`` and the ``webclient`` service
    is used to build it.
"""
import logging
from pathlib import Path

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

INDEX_RESOURCE_NAME = "statics.index"

log = logging.getLogger(__file__)


def get_client_outdir(app: web.Application) -> Path:
    cfg = app[APP_CONFIG_KEY]["main"]

    # pylint 2.3.0 produces 'E1101: Instance of 'Path' has no 'expanduser' member (no-member)' ONLY
    # with the installed code and not with the development code!
    client_dir = Path(cfg["client_outdir"]).expanduser() #pylint: disable=E1101
    if not client_dir.exists():
        txt = reason = "Front-end application is not available"
        if cfg["testing"]:
            reason = "Invalid client source path: %s" % client_dir
        raise web.HTTPServiceUnavailable(reason=reason, text=txt)
    return client_dir

async def index(request: web.Request):
    """
        Serves boot application under index
    """
    log.debug("index.request:\n %s", request)

    index_path = get_client_outdir(request.app) / "index.html"
    with index_path.open() as ofh:
        return web.Response(text=ofh.read(), content_type="text/html")

def setup_statics(app: web.Application):
    log.debug("Setting up %s ...", __name__)


    # TODO: Should serving front-end ria be configurable?
    # Front-end Rich Interface Application (RIA)
    try:
        outdir = get_client_outdir(app)

        # Checks integrity of RIA source before serving
        EXPECTED_FOLDERS = ('osparc', 'resource', 'transpiled')
        folders = [x for x in outdir.iterdir() if x.is_dir()]

        for name in EXPECTED_FOLDERS:
            folder_names = [path.name for path in folders]
            if name not in folder_names:
                raise web.HTTPServiceUnavailable(
                    reason="Invalid front-end source-output folders" \
                    " Expected %s, got %s in %s" %(EXPECTED_FOLDERS, folder_names, outdir),
                    text ="Front-end application is not available"
                )

        # TODO: map ui to /ui or create an alias!?
        app.router.add_get("/", index, name=INDEX_RESOURCE_NAME)

        # NOTE: source-output and build-output have both the same subfolder structure
        # TODO: check whether this can be done at oncen
        for path in folders:
            app.router.add_static('/' + path.name, path)

    except web.HTTPServiceUnavailable as ex:
        log.exception(ex.text)
        return
