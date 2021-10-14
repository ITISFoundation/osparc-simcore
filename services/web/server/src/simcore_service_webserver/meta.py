""" Meta-modeling app module

    Manages version control of studies, both the project document and the associated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from .constants import APP_SETTINGS_KEY
from .director_v2_api import get_run_policy, set_run_policy
from .meta_projects import MetaProjectRunPolicy, projects_redirection_middleware
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=[
        "simcore_service_webserver.projects",
        "simcore_service_webserver.version_control",
    ],
    logger=log,
)
def setup_meta(app: web.Application):

    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    if not settings.WEBSERVER_DEV_FEATURES_ENABLED:
        raise SkipModuleSetup(reason="Development feature")

    # TODO: app.add_routes(meta_handlers.routes)
    app.middlewares.append(projects_redirection_middleware)

    # Overrides run-policy from directorv2
    assert get_run_policy(app)  # nosec
    set_run_policy(app, MetaProjectRunPolicy())
