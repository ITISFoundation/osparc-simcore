import logging

from aiohttp import web

from ...login.decorators import login_required
from .._controller.rest.redirects import get_redirection_to_viewer
from ..settings import StudiesDispatcherSettings
from .rest.nih import routes as nih_routes
from .rest.redirects import get_redirection_to_viewer

_logger = logging.getLogger(__name__)


def setup_controller(app: web.Application, settings: StudiesDispatcherSettings):
    # routes
    redirect_handler = get_redirection_to_viewer
    if settings.is_login_required():
        redirect_handler = login_required(get_redirection_to_viewer)

        _logger.info(
            "'%s' config explicitly disables anonymous users from this feature",
            __name__,
        )

    app.router.add_routes(
        [web.get("/view", redirect_handler, name="get_redirection_to_viewer")]
    )

    app.router.add_routes(nih_routes)
