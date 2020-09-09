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
from typing import Set

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .settings import APP_SETTINGS_KEY

INDEX_RESOURCE_NAME = "statics.index"
TMPDIR_KEY = f"{__name__}.tmpdir"

log = logging.getLogger(__file__)


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


async def index(request: web.Request):
    """
    Serves boot application under index
    """
    log.debug("index.request:\n %s", request)

    index_path = get_client_outdir(request.app) / "index.html"
    with index_path.open() as ofh:
        return web.Response(text=ofh.read(), content_type="text/html")


def write_statics_file(app: web.Application, directory: Path) -> None:
    # ensures directory exists
    os.makedirs(directory, exist_ok=True)

    # create statics field
    statics = {}

    # TODO: build with pydantic and validate data before serializing
    statics["stackName"] = os.environ.get("SWARM_STACK_NAME")
    statics["buildDate"] = os.environ.get("BUILD_DATE")

    # Urls to manuals
    statics["manualMainURL"] = os.environ.get(
        "WEBSERVER_MANUAL_MAIN_URL", "http://docs.osparc.io/"
    )
    statics["manualExtraURL"] = os.environ.get("WEBSERVER_MANUAL_EXTRA_URL")

    # Fogbugz tickets
    # SEE https://support.fogbugz.com/hc/en-us/articles/360011241594-Generating-a-Case-Template-with-bookmarklets
    # https://<your_fogbugz_URL>.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=<project-id>&ixArea=<area_id>&ixCategory=<category_id>&ixPersonAssignedTo=<assigned_user_id>&sTitle=<title_of_case>&sEvent=<body_of text>
    statics["fogbugzOriginURL"] = os.environ.get("WEBSERVER_FOGBUGZ_URL", "https://z43.fogbugz.com")
    statics["fogbugzProjectId"] = os.environ.get("WEBSERVER_FOGBUGZ_PROJECT_ID")

    # Extra url to form (e.g. google forms for fogbugz public submission form)
    statics["feedbackFormURL"] = os.environ.get("WEBSERVER_FEEDBACK_FORM_URL")


    statics["buildDate"] = app[APP_SETTINGS_KEY].build_date
    statics.update(app[APP_SETTINGS_KEY].public_dict())

    with open(directory / "statics.json", "wt") as fh:
        json.dump(statics, fh)


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup_statics(app: web.Application):
    # Serves Front-end Rich Interface Application (RIA)
    app.router.add_get("/", index, name=INDEX_RESOURCE_NAME)

    # NOTE: source-output and build-output have both the same subfolder structure
    outdir: Path = get_client_outdir(app)

    # Create statics file
    write_statics_file(app, outdir / "resource")

    required_dirs = ["osparc", "resource", "transpiled"]
    folders = [x for x in outdir.iterdir() if x.is_dir()]

    # Checks integrity of RIA source before serving and warn!
    for name in required_dirs:
        folder_names = [path.name for path in folders]
        if name not in folder_names:
            log.warning(
                "Missing folders: expected %s, got %s in %s",
                required_dirs,
                folder_names,
                outdir,
            )

    # Add static routes
    folders: Set[Path] = set(folders).union([outdir / name for name in required_dirs])
    for path in folders:
        app.router.add_static("/" + path.name, path)

    # cleanup
    app.on_cleanup.append(_delete_tmps)
