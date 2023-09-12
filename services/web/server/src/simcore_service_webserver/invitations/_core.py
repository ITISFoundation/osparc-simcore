import logging
from contextlib import contextmanager
from typing import Final

import sqlalchemy as sa
from aiohttp import ClientError, ClientResponseError, web
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationContentAndLink,
    ApiInvitationInputs,
)
from models_library.users import GroupID
from pydantic import AnyHttpUrl, ValidationError, parse_obj_as
from servicelib.error_codes import create_error_code
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.users import users

from ..db.plugin import get_database_engine
from ..products.api import Product
from ._client import (
    InvitationsServiceApi,
    get_invitations_service_api,
)
from .errors import (
    MSG_INVALID_INVITATION_URL,
    MSG_INVITATION_ALREADY_USED,
    InvalidInvitation,
    InvitationsErrors,
    InvitationsServiceUnavailable,
)

_logger = logging.getLogger(__name__)


async def _is_user_registered_in_product(
    app: web.Application, email: str, product_group_id: GroupID
) -> bool:
    pg_engine = get_database_engine(app=app)

    async with pg_engine.acquire() as conn:
        user_id = await conn.scalar(
            sa.select(users.c.id)
            .select_from(
                sa.join(user_to_groups, users, user_to_groups.c.uid == users.c.id)
            )
            .where(
                (users.c.email == email) & (user_to_groups.c.gid == product_group_id)
            )
        )
        return user_id is not None


@contextmanager
def _handle_exceptions_as_invitations_errors():
    try:
        yield  # API function calls happen

    except ClientResponseError as err:
        # check possible errors
        if err.status == web.HTTPUnprocessableEntity.status_code:
            error_code = create_error_code(err)
            _logger.exception(
                "Invitation request %s unexpectedly failed [%s]",
                f"{err=} ",
                f"{error_code}",
                extra={"error_code": error_code},
            )
            raise InvalidInvitation(reason=f"Unexpected error [{error_code}]") from err

        assert err.status >= 400  # nosec
        # any other error status code
        raise InvitationsServiceUnavailable from err

    except (ValidationError, ClientError) as err:
        raise InvitationsServiceUnavailable from err

    except InvitationsErrors:
        # bypass: prevents that the Exceptions handler catches this exception
        raise

    except Exception as err:
        _logger.exception("Unexpected error in invitations plugin")
        raise InvitationsServiceUnavailable from err


#
# API plugin CALLS
#

_LONG_CODE_LEN: Final[int] = 100  # typically long strings


def is_service_invitation_code(code: str):
    """Fast check to distinguish from confirmation-type of invitation code"""
    return len(code) > _LONG_CODE_LEN


async def validate_invitation_url(
    app: web.Application,
    guest_email: str,
    current_product: Product,
    invitation_url: str,
) -> ApiInvitationContent:
    """Validates invitation and associated email/user and returns content upon success

    raises InvitationsError
    """
    if current_product.group_id is None:
        raise InvitationsServiceUnavailable(
            reason="Current product is not configured for invitations"
        )

    invitations_service: InvitationsServiceApi = get_invitations_service_api(app=app)

    with _handle_exceptions_as_invitations_errors():
        try:
            valid_url = parse_obj_as(AnyHttpUrl, invitation_url)
        except ValidationError as err:
            raise InvalidInvitation(reason=MSG_INVALID_INVITATION_URL) from err

        # check with service
        invitation = await invitations_service.extract_invitation(
            invitation_url=valid_url
        )

        if invitation.guest != guest_email:
            raise InvalidInvitation(
                reason="This invitation was issued for a different email"
            )

        if (
            invitation.product is not None
            and invitation.product != current_product.name
        ) or current_product.group_id is None:
            raise InvalidInvitation(
                reason="This invitation was issued for a different product"
            )

        # existing users cannot be re-invited
        if await _is_user_registered_in_product(
            app=app, email=invitation.guest, product_group_id=current_product.group_id
        ):
            raise InvalidInvitation(reason=MSG_INVITATION_ALREADY_USED)

    return invitation


async def extract_invitation(
    app: web.Application, invitation_url: str
) -> ApiInvitationContent:
    """Validates invitation and returns content without checking associated user

    raises InvitationsError
    """
    invitations_service: InvitationsServiceApi = get_invitations_service_api(app=app)

    with _handle_exceptions_as_invitations_errors():
        try:
            valid_url = parse_obj_as(AnyHttpUrl, invitation_url)
        except ValidationError as err:
            raise InvalidInvitation(reason=MSG_INVALID_INVITATION_URL) from err

        # check with service
        return await invitations_service.extract_invitation(invitation_url=valid_url)


async def generate_invitation(
    app: web.Application, params: ApiInvitationInputs
) -> ApiInvitationContentAndLink:
    invitations_service: InvitationsServiceApi = get_invitations_service_api(app=app)

    with _handle_exceptions_as_invitations_errors():
        # check with service
        return await invitations_service.generate_invitation(params)
