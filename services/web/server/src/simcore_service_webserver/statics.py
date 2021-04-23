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
from functools import lru_cache
from pathlib import Path
from typing import Dict

from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from tenacity import after_log, retry, stop_after_attempt, wait_random

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
)

STATIC_DIRNAMES = FRONTEND_APPS_AVAILABLE | {"resource", "transpiled"}

APP_FRONTEND_BASEDIR_KEY = f"{__name__}.frontend_basedir"
APP_STATICS_OUTDIR_KEY = f"{__file__}.outdir"


log = logging.getLogger(__file__)


@lru_cache()
def get_index_body(statics_outdir: Path, frontend_name: str):
    index_path = statics_outdir / frontend_name / "index.html"
    html = index_path.read_text()
    # TODO: this is not very safe ...
    # fixes relative paths
    html = html.replace(f"../resource/{frontend_name}", f"resource/{frontend_name}")
    html = html.replace("boot.js", f"{frontend_name}/boot.js")
    return html


async def get_frontend_ria(request: web.Request):
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
    statics_outdir: Path = request.app[APP_STATICS_OUTDIR_KEY]
    return web.Response(
        body=get_index_body(statics_outdir, target_frontend), content_type="text/html"
    )


def create_statics_settings(app) -> Dict:
    # Adds general server settings
    info: Dict = app[APP_SETTINGS_KEY].to_client_statics()

    # Adds specifics to front-end app
    info.update(FrontEndAppSettings().to_statics())

    return info


async def _start_statics(app: web.Application):
    # NOTE: in devel model, the folder might be under construction
    # (qx-compile takes time), therefore we create statics.json
    # on_startup instead of upon setup

    resource_dir: Path = app[APP_STATICS_OUTDIR_KEY] / "resource"
    statics_settings: Dict = create_statics_settings(app)

    @retry(
        wait=wait_random(min=1, max=3),
        stop=stop_after_attempt(3),
        after=after_log(log, logging.WARNING),
    )
    async def do_write_statics_file() -> None:
        with open(resource_dir / "statics.json", "wt") as fh:
            json.dump(statics_settings, fh)

    # Creating static info
    await do_write_statics_file()


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup_statics(app: web.Application):

    # NOTE: source-output and build-output have both the same subfolder structure
    cfg = app[APP_CONFIG_KEY]["main"]
    app[APP_STATICS_OUTDIR_KEY] = statics_dir = Path(cfg["client_outdir"]).expanduser()

    # Creating static routes
    routes = web.RouteTableDef()
    is_dev: bool = app[APP_SETTINGS_KEY].build_target in [None, "development"]
    for name in STATIC_DIRNAMES:
        folder = statics_dir / name

        # avoids problems restarting when qx-compile takes longer to product outputs
        if not folder.exists() and is_dev:
            os.makedirs(folder, exist_ok=True)

        # can navigate file index in dev mode
        routes.static(f"/{folder.name}", folder, show_index=is_dev)
    app.add_routes(routes)

    # Create dynamic route to serve front-end client
    app.router.add_get("/", get_frontend_ria, name=INDEX_RESOURCE_NAME)

    # Delayed creation of statics.json (mostly for dev mode)
    app.on_startup.append(_start_statics)
