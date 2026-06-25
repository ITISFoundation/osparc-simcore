import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..products.plugin import setup_products
from ._controller import setup_controller
from ._projects_permalinks import setup_projects_permalinks
from ._studies_access import get_redirection_to_study_page
from .settings import StudiesDispatcherSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


def _setup_studies_access(app: web.Application, _settings: StudiesDispatcherSettings):
    # The handler manages login-required logic internally and always redirects to the
    # SPA error page — never returning a raw HTTP response. Middleware filtering is a
    # deferred concern for a future refactoring pass.
    #
    # The alias handles cases where TLD like sarvalidations.site are redirected to a study or template
    # According to RFC 3986, the trailing slash in URLs with paths is part of the path and should be treated as a
    # different resource.
    # However, the trailing slash in case of a TLD is not a different resource, with and without slash are identical.
    # To handle this special case, we add a route with a trailing slash to redirect to the same handler as the one
    # without a trailing slash.
    app.router.add_routes(
        [
            web.get(r"/study/{id}", get_redirection_to_study_page, name="get_redirection_to_study_page"),
            web.get(r"/study/{id}/", get_redirection_to_study_page, name="get_redirection_to_study_page_with_slash"),
        ]
    )


@app_setup_func(
    "simcore_service_webserver.studies_dispatcher",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_STUDIES_DISPATCHER",
    logger=_logger,
)
def setup_studies_dispatcher(app: web.Application) -> bool:
    settings: StudiesDispatcherSettings = get_plugin_settings(app)

    # setup other plugins
    setup_products(app=app)

    # setup internal modules
    _setup_studies_access(app, settings)
    setup_projects_permalinks(app, settings)

    # rest controllers
    setup_controller(app, settings)

    return True
