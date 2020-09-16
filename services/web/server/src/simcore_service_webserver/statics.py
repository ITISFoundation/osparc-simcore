""" Serves client's code

    - The client-side runs a RIA (Rich Interface Application) so the server does not
    need to render pages upon request but only serve once the code to the client.
    - The client application then interacts with the server via a http and/or socket API
    - The client application is under ``services/web/client`` and the ``webclient`` service
    is used to build it.
"""
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .constants import APP_SETTINGS_KEY, RQ_PRODUCT_KEY, RQ_PRODUCT_FRONTEND_KEY

FRONTEND_APPS_AVAILABLE = {"osparc", "tis", "s4l"}
FRONTEND_APP_DEFAULT = "osparc"

INDEX_RESOURCE_NAME = "statics.index"
TMPDIR_KEY = f"{__name__}.tmpdir"

log = logging.getLogger(__file__)

assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE  # nosec


def get_client_outdir(app: web.Application) -> Path:
    cfg = app[APP_CONFIG_KEY]["main"]
    client_dir = Path(cfg["client_outdir"]).expanduser()
    if not client_dir.exists():
        tmp_dir = tempfile.mkdtemp(suffix="client_outdir")
        log.error(
            "Invalid client source path [%s]. Defaulting to %s", client_dir, tmp_dir
        )
        client_dir = tmp_dir
        app[TMPDIR_KEY] = tmp_dir
    return client_dir


async def _delete_tmps(app: web.Application):
    tmp_dir = app.get(TMPDIR_KEY)
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def get_frontend_ria(request: web.Request):
    log.debug("Request from host %s", request.headers["Host"])
    target_frontend = request[RQ_PRODUCT_FRONTEND_KEY]

    if target_frontend is None:
        log.warning("No front-end specified using default %s", FRONTEND_APP_DEFAULT)
        target_frontend = FRONTEND_APP_DEFAULT

    elif target_frontend not in FRONTEND_APPS_AVAILABLE:
        raise web.HTTPNotFound(
            reason=f"Requested front-end '{target_frontend}' is not available"
        )

    log.debug(
        "Serving front-end %s for product %s", request[RQ_PRODUCT_KEY], target_frontend
    )
    raise web.HTTPFound(f"/{target_frontend}/index.html#")


def write_statics_file(app: web.Application, directory: Path) -> None:
    # ensures directory exists
    os.makedirs(directory, exist_ok=True)

    # create statics field
    statics = app[APP_SETTINGS_KEY].to_client_statics()
    with open(directory / "statics.json", "wt") as fh:
        json.dump(statics, fh)


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup_statics(app: web.Application):

    # Serves Front-end Rich Interface Application (RIA)
    app.router.add_get("/", get_frontend_ria, name=INDEX_RESOURCE_NAME)

    # NOTE: source-output and build-output have both the same subfolder structure
    frontend_outdir: Path = get_client_outdir(app)

    # Creating static info about server
    write_statics_file(app, frontend_outdir / "resource")

    # Creating static routes
    routes = web.RouteTableDef()
    static_dirs = FRONTEND_APPS_AVAILABLE | {"resource", "transpiled"}
    is_dev: bool = app[APP_SETTINGS_KEY].build_target in [None, "development"]

    for name in static_dirs:
        folder = frontend_outdir / name
        routes.static(f"/{folder.name}", folder, show_index=is_dev)

    app.add_routes(routes)

    # cleanup
    app.on_cleanup.append(_delete_tmps)
