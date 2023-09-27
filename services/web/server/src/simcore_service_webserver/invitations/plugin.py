"""
    Plugin to interact with the invitations service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_service_webserver.products.plugin import setup_products

from .._constants import APP_SETTINGS_KEY
from ..db.plugin import setup_db
from . import _handlers
from ._client import invitations_service_api_cleanup_ctx
from ._core import (
    extract_invitation,
    is_service_invitation_code,
    validate_invitation_url,
)

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_INVITATIONS",
    logger=_logger,
)
def setup_invitations(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS  # nosec

    setup_db(app)
    setup_products(app)

    app.router.add_routes(_handlers.routes)

    app.cleanup_ctx.append(invitations_service_api_cleanup_ctx)


#
# API plugin
#

__all__: tuple[str, ...] = (
    "extract_invitation",
    "is_service_invitation_code",
    "setup_invitations",
    "validate_invitation_url",
)
# nopycln: file
