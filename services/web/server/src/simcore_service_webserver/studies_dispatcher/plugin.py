import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..login.decorators import login_required
from ..products.plugin import setup_products
from ._controller import setup_controller
from ._projects_permalinks import setup_projects_permalinks
from ._studies_access import get_redirection_to_study_page
from .settings import StudiesDispatcherSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


def _setup_studies_access(app: web.Application, settings: StudiesDispatcherSettings):
    # Redirects routes
    study_handler = get_redirection_to_study_page
    if settings.is_login_required():
        study_handler = login_required(get_redirection_to_study_page)

    # NOTE: these routes bypass the REST error/envelope middleware (is_api_request matches only /v0),
    # so handler errors surface as a 302 redirect instead of a 5xx status.
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6477
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6476
    app.router.add_routes(
        [
            web.get(r"/study/{id}", study_handler, name="get_redirection_to_study_page"),
            web.get(r"/study/{id}/", study_handler, name="get_redirection_to_study_page_with_slash"),
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
