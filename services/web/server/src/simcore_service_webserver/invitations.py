"""
    Plugin to interact with the invitations service
"""

import logging

from aiohttp import ClientResponseError, web
from pydantic.errors import PydanticErrorMixin
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import APP_SETTINGS_KEY
from .invitations_client import (
    InvitationsServiceApi,
    get_invitations_service_api,
    invitations_service_api_cleanup_ctx,
)

logger = logging.getLogger(__name__)

#
# API plugin errors
#


class InvitationsErrors(PydanticErrorMixin, ValueError):
    ...


class InvalidInvitationError(InvitationsErrors):
    msg_template = "Invalid invitation: {reason}"


class InvitationServiceUnavailable(InvitationsErrors):
    msg_template = "Invitations service is currently unavailable"


#
# API plugin calls
#


async def validate_invitation_url(request: web.Request, invitation_url: str):
    # extract invitation
    invitations_api: InvitationsServiceApi = get_invitations_service_api(
        app=request.app
    )

    # check possible errors
    try:
        invitation = await invitations_api.extract_invitation(
            invitation_url=invitation_url
        )

    except ClientResponseError as err:
        if err.status == web.HTTPUnprocessableEntity.status_code:
            raise InvalidInvitationError(reason=err.message) from err
        raise InvitationServiceUnavailable() from err

    # TODO: expired?

    if not invitation.guest:
        # TODO: check if user exists or not
        raise InvalidInvitationError(reason="This user was already invited")


#
# SETUP
#


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_INVITATIONS",
    logger=logger,
)
def setup_invitations(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS  # nosec

    app.cleanup_ctx.append(invitations_service_api_cleanup_ctx)


# TODO:
# login plugin ensures setup_invitations are in place (if not, deactivates invitations?)
# - ``check_and_consume_invitation``: Check in this order:
#     - invitation in confirmation table
#     - invitation in invitations service
#
#

#
# API plugin
#
__all__: tuple[str, ...] = (
    "setup_invitations",
    "validate_invitation_url",
    "InvalidInvitationError",
    "InvitationServiceUnavailable",
)
