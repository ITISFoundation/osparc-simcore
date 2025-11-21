import logging
from urllib.parse import quote

from aiohttp import web
from simcore_service_webserver.login._application_keys import (
    CONFIRMATION_SERVICE_APPKEY,
)
from simcore_service_webserver.login.settings import get_plugin_options
from yarl import URL

from ..application_setup import ensure_single_setup
from ..db.plugin import get_asyncpg_engine
from ._confirmation_repository import ConfirmationRepository
from ._confirmation_service import ConfirmationService

_logger = logging.getLogger(__name__)


def _url_for_confirmation(app: web.Application, code: str) -> URL:
    # NOTE: this is in a query parameter, and can contain ? for example.
    safe_code = quote(code, safe="")
    return app.router["auth_confirmation"].url_for(code=safe_code)


def make_confirmation_link(request: web.Request, code: str) -> str:
    assert code  # nosec
    link = _url_for_confirmation(request.app, code=code)
    return f"{request.scheme}://{request.host}{link}"


@ensure_single_setup(__name__, logger=_logger)
def setup_confirmation(app: web.Application) -> None:
    """Sets up the confirmation service in the application."""

    async def _on_cleanup_ctx(app: web.Application):
        repository = ConfirmationRepository(get_asyncpg_engine(app))
        options = get_plugin_options(app)
        app[CONFIRMATION_SERVICE_APPKEY] = ConfirmationService(repository, options)

        yield

    app.cleanup_ctx.append(_on_cleanup_ctx)
