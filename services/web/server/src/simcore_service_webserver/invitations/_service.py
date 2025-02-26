import logging
from typing import Final

from aiohttp import web
from models_library.api_schemas_invitations.invitations import (
    ApiInvitationContent,
    ApiInvitationContentAndLink,
    ApiInvitationInputs,
)
from models_library.emails import LowerCaseEmailStr
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from ..groups.api import is_user_by_email_in_group
from ..products.products_service import Product
from ._client import get_invitations_service_api
from .errors import (
    MSG_INVALID_INVITATION_URL,
    MSG_INVITATION_ALREADY_USED,
    InvalidInvitationError,
    InvitationsServiceUnavailableError,
)

_logger = logging.getLogger(__name__)


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

    Raises:
        InvitationsError
        InvalidInvitationError:
        InvitationsServiceUnavailableError:
    """
    if current_product.group_id is None:
        raise InvitationsServiceUnavailableError(
            reason="Current product is not configured for invitations"
        )

    try:
        valid_url = TypeAdapter(AnyHttpUrl).validate_python(invitation_url)
    except ValidationError as err:
        raise InvalidInvitationError(reason=MSG_INVALID_INVITATION_URL) from err

    # check with service
    invitation: ApiInvitationContent = await get_invitations_service_api(
        app=app
    ).extract_invitation(invitation_url=valid_url)

    # check email
    if invitation.guest.lower() != guest_email.lower():
        raise InvalidInvitationError(
            reason="This invitation was issued for a different email"
        )

    # check product
    assert current_product.group_id is not None  # nosec
    if invitation.product is not None and invitation.product != current_product.name:
        raise InvalidInvitationError(
            reason="This invitation was issued for a different product. "
            f"Got '{invitation.product}', expected '{current_product.name}'"
        )

    # check invitation used
    assert invitation.product == current_product.name  # nosec
    is_user_registered_in_product: bool = await is_user_by_email_in_group(
        app,
        user_email=LowerCaseEmailStr(invitation.guest),
        group_id=current_product.group_id,
    )
    if is_user_registered_in_product:
        # NOTE: a user might be already registered but the invitation is for another product
        raise InvalidInvitationError(reason=MSG_INVITATION_ALREADY_USED)

    return invitation


async def extract_invitation(
    app: web.Application, invitation_url: str
) -> ApiInvitationContent:
    """Validates invitation and returns content without checking associated user

    Raises:
        InvitationsError
        InvalidInvitationError:
        InvitationsServiceUnavailableError:
    """
    try:
        valid_url = TypeAdapter(AnyHttpUrl).validate_python(invitation_url)
    except ValidationError as err:
        raise InvalidInvitationError(reason=MSG_INVALID_INVITATION_URL) from err

    # check with service
    invitation: ApiInvitationContent = await get_invitations_service_api(
        app=app
    ).extract_invitation(invitation_url=valid_url)
    return invitation


async def generate_invitation(
    app: web.Application, params: ApiInvitationInputs
) -> ApiInvitationContentAndLink:
    """
    Raises:
        InvitationsError
        InvalidInvitationError:
        InvitationsServiceUnavailableError:
    """
    invitation: ApiInvitationContentAndLink = await get_invitations_service_api(
        app=app
    ).generate_invitation(params)
    return invitation
