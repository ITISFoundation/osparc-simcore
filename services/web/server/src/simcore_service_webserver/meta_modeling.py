""" Meta-modeling app module

    Manages version control of studies, both the project document and the associated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import meta_modeling_handlers
from ._constants import APP_SETTINGS_KEY
from .director_v2_api import get_project_run_policy, set_project_run_policy
from .meta_modeling_projects import meta_project_policy, projects_redirection_middleware

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=[
        "simcore_service_webserver.projects",
        ## FIXME: tmp disabled so it can start "simcore_service_webserver.version_control",
    ],
    settings_name="WEBSERVER_META_MODELING",
    logger=log,
)
def setup_meta_modeling(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_META_MODELING

    app.add_routes(meta_modeling_handlers.routes)
    app.middlewares.append(projects_redirection_middleware)

    # Overrides run-policy from directorv2
    assert get_project_run_policy(app)  # nosec
    set_project_run_policy(app, meta_project_policy)
