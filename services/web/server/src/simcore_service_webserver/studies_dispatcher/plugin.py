import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY
from ..login.decorators import login_required
from ..products import setup_products
from ._studies_access import get_redirection_to_study_page
from .handlers_redirects import get_redirection_to_viewer
from .handlers_rest import rest_handler_functions
from .settings import StudiesDispatcherSettings, get_plugin_settings

logger = logging.getLogger(__name__)


def _setup_studies_access(app: web.Application, settings: StudiesDispatcherSettings):
    # TODO: integrate when _studies_access is fully integrated

    # Redirects routes
    study_handler = get_redirection_to_study_page
    if settings.is_login_required():
        study_handler = login_required(get_redirection_to_study_page)

    # TODO: make sure that these routes are filtered properly in active middlewares
    app.router.add_routes(
        [
            web.get(r"/study/{id}", study_handler, name="study"),
        ]
    )


@app_module_setup(
    "simcore_service_webserver.studies_dispatcher",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_STUDIES_DISPATCHER",
    logger=logger,
)
def setup_studies_dispatcher(app: web.Application) -> bool:
    settings: StudiesDispatcherSettings = get_plugin_settings(app)

    setup_products(app=app)

    _setup_studies_access(app, settings)

    # Redirects routes
    redirect_handler = get_redirection_to_viewer
    if settings.is_login_required():
        redirect_handler = login_required(get_redirection_to_viewer)

        logger.info(
            "'%s' config explicitly disables anonymous users from this feature",
            __name__,
        )

    app.router.add_routes(
        [web.get("/view", redirect_handler, name="get_redirection_to_viewer")]
    )

    # Rest-API routes: maps handlers with routes tags with "viewer" based on OAS operation_id
    specs = app[APP_OPENAPI_SPECS_KEY]
    rest_routes = map_handlers_with_operations(
        rest_handler_functions,
        filter(lambda op: "viewer" in op.tags, iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(rest_routes)

    return True
