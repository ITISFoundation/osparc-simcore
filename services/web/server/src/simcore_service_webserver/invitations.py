"""
    Plugin to interact with the invitations service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import APP_SETTINGS_KEY
from .db import setup_db
from .invitations_client import invitations_service_api_cleanup_ctx
from .invitations_core import (
    InvalidInvitation,
    InvitationsServiceUnavailable,
    extract_invitation,
    is_service_invitation_code,
    validate_invitation_url,
)

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_INVITATIONS",
    logger=logger,
)
def setup_invitations(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS  # nosec

    setup_db(app)

    app.cleanup_ctx.append(invitations_service_api_cleanup_ctx)


#
# API plugin
#

__all__: tuple[str, ...] = (
    "extract_invitation",
    "InvalidInvitation",
    "InvitationsServiceUnavailable",
    "is_service_invitation_code",
    "setup_invitations",
    "validate_invitation_url",
)
# nopycln: file
