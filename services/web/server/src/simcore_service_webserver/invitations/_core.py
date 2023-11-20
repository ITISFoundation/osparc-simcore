import logging
from contextlib import contextmanager
from typing import Final

from aiohttp import ClientError, ClientResponseError, web
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationContentAndLink,
    ApiInvitationInputs,
)
from pydantic import AnyHttpUrl, ValidationError, parse_obj_as
from servicelib.error_codes import create_error_code

from ..products.api import Product
from ._client import InvitationsServiceApi, get_invitations_service_api
from ._db import is_user_registered_in_product
from .errors import (
    MSG_INVALID_INVITATION_URL,
    MSG_INVITATION_ALREADY_USED,
    InvalidInvitation,
    InvitationsErrors,
    InvitationsServiceUnavailable,
)

_logger = logging.getLogger(__name__)


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
        _logger.debug("Invitations error %s", f"{err}")
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
    *,
    current_product: Product,
    guest_email: str,
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

        # check email
        if invitation.guest != guest_email:
            raise InvalidInvitation(
                reason="This invitation was issued for a different email"
            )

        # check product
        assert current_product.group_id is not None  # nosec
        if (
            invitation.product is not None
            and invitation.product != current_product.name
        ):
            raise InvalidInvitation(
                reason="This invitation was issued for a different product. "
                f"Got '{invitation.product}', expected '{current_product.name}'"
            )

        # check invitation used
        assert invitation.product == current_product.name  # nosec
        if await is_user_registered_in_product(
            app=app, email=invitation.guest, product_group_id=current_product.group_id
        ):
            # NOTE: a user might be already registered but the invitation is for another product
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
