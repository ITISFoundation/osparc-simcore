"""
    Plugin to interact with the invitations service
"""

import logging
from contextlib import contextmanager

import sqlalchemy as sa
from aiohttp import ClientError, ClientResponseError, web
from pydantic import ValidationError
from pydantic.errors import PydanticErrorMixin
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_postgres_database.models.users import users

from ._constants import APP_SETTINGS_KEY
from .db import get_database_engine, setup_db
from .invitations_client import (
    InvitationContent,
    InvitationsServiceApi,
    get_invitations_service_api,
    invitations_service_api_cleanup_ctx,
)

logger = logging.getLogger(__name__)


#
# database
#


async def _is_user_registered(app: web.Application, email: str) -> bool:
    pg_engine = get_database_engine(app=app)

    async with pg_engine.acquire() as conn:
        user_id = await conn.scalar(
            sa.select([users.c.id]).where(users.c.email == email)
        )
        return user_id is not None


#
# API plugin errors
#


class InvitationsErrors(PydanticErrorMixin, ValueError):
    ...


class InvalidInvitationError(InvitationsErrors):
    msg_template = "Invalid invitation: {reason}"


class InvitationServiceUnavailable(InvitationsErrors):
    msg_template = "Invitations service is currently unavailable"


@contextmanager
def _handle_exceptions_as_invitations_errors():
    try:

        yield  # API function calls happen

    except ClientResponseError as err:
        # check possible errors
        if err.status == web.HTTPUnprocessableEntity.status_code:
            raise InvalidInvitationError(reason=err.message) from err

        # some validation or other error?
        raise InvitationServiceUnavailable() from err

    except ValidationError as err:
        raise InvitationServiceUnavailable() from err

    except ClientError as err:
        raise InvitationServiceUnavailable() from err

    except InvitationsErrors:
        # bypass
        raise

    except Exception as err:
        logger.exception("Unexpected error in invitations plugin")
        raise InvitationServiceUnavailable() from err


#
# API plugin calls
#


async def validate_invitation_url(
    app: web.Application, invitation_url: str
) -> InvitationContent:
    """Validates invitation and returns content

    raises InvitationsError
    """
    invitations_service: InvitationsServiceApi = get_invitations_service_api(app=app)

    with _handle_exceptions_as_invitations_errors():

        # check with service
        invitation = await invitations_service.extract_invitation(
            invitation_url=invitation_url
        )

        # existing users cannot be re-invited
        if await _is_user_registered(app=app, email=invitation.guest):
            raise InvalidInvitationError(reason="This invitation was already used")

    return invitation


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

    setup_db(app)

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
