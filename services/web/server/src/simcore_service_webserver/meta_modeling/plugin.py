""" Meta-modeling app module

    Manages version control of studies, both the project document and the associated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from ..director_v2.api import get_project_run_policy, set_project_run_policy
from . import _handlers
from ._projects import meta_project_policy, projects_redirection_middleware

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=[
        "simcore_service_webserver.projects",
    ],
    settings_name="WEBSERVER_META_MODELING",
    logger=log,
)
def setup_meta_modeling(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_META_MODELING  # nosec

    log.warning(
        "'meta_modeling' plugin is STILL UNDER DEVELOPMENT and should not be used in production."
        "Can only be activated with WEBSERVER_DEV_FEATURES_ENABLED=1"
    )

    app.add_routes(_handlers.routes)
    app.middlewares.append(projects_redirection_middleware)

    # Overrides run-policy from directorv2
    assert get_project_run_policy(app)  # nosec
    set_project_run_policy(app, meta_project_policy)
