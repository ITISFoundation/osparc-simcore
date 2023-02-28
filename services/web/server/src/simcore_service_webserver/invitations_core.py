"""
    Plugin to interact with the invitations service
"""

import logging
from contextlib import contextmanager

import sqlalchemy as sa
from aiohttp import ClientError, ClientResponseError, web
from pydantic import ValidationError
from pydantic.errors import PydanticErrorMixin
from simcore_postgres_database.models.users import users

from .db import get_database_engine
from .invitations_client import (
    InvitationContent,
    InvitationsServiceApi,
    get_invitations_service_api,
)

logger = logging.getLogger(__name__)


#
# DATABASE
#


async def _is_user_registered(app: web.Application, email: str) -> bool:
    pg_engine = get_database_engine(app=app)

    async with pg_engine.acquire() as conn:
        user_id = await conn.scalar(
            sa.select([users.c.id]).where(users.c.email == email)
        )
        return user_id is not None


#
# API plugin ERRORS
#


class InvitationsErrors(PydanticErrorMixin, ValueError):
    ...


class InvalidInvitation(InvitationsErrors):
    msg_template = "Invalid invitation: {reason}"


class InvitationsServiceUnavailable(InvitationsErrors):
    msg_template = (
        "Unable to process your invitation since the invitations service is currently unavailable. "
        "Please try again later."
    )


@contextmanager
def _handle_exceptions_as_invitations_errors():
    try:

        yield  # API function calls happen

    except ClientResponseError as err:
        # check possible errors
        if err.status == web.HTTPUnprocessableEntity.status_code:
            raise InvalidInvitation(reason=err.message) from err

        assert 400 <= err.status  # nosec
        # any other error status code
        raise InvitationsServiceUnavailable() from err

    except (ValidationError, ClientError) as err:
        raise InvitationsServiceUnavailable() from err

    except InvitationsErrors:
        # bypass: prevents that the Exceptions handler catches this exception
        raise

    except Exception as err:
        logger.exception("Unexpected error in invitations plugin")
        raise InvitationsServiceUnavailable() from err


#
# API plugin CALLS
#


def is_service_invitation_code(code: str):
    """Fast check to distinguish from confirmation-type of invitation code"""
    return len(code) > 100  # typically long strings


async def validate_invitation_url(
    app: web.Application, guest_email: str, invitation_url: str
) -> InvitationContent:
    """Validates invitation and associated email/user and returns content upon success

    raises InvitationsError
    """
    invitations_service: InvitationsServiceApi = get_invitations_service_api(app=app)

    with _handle_exceptions_as_invitations_errors():

        # check with service
        invitation = await invitations_service.extract_invitation(
            invitation_url=invitation_url
        )

        if invitation.guest != guest_email:
            raise InvalidInvitation(
                reason="This invitation was issued for a different email"
            )

        # existing users cannot be re-invited
        if await _is_user_registered(app=app, email=invitation.guest):
            raise InvalidInvitation(reason="This invitation was already used")

    return invitation


async def extract_invitation(
    app: web.Application, invitation_url: str
) -> InvitationContent:
    """Validates invitation and returns content without checking associated user

    raises InvitationsError
    """
    invitations_service: InvitationsServiceApi = get_invitations_service_api(app=app)

    with _handle_exceptions_as_invitations_errors():

        # check with service
        invitation = await invitations_service.extract_invitation(
            invitation_url=invitation_url
        )
        return invitation
