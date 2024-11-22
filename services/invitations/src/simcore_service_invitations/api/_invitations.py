import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasicCredentials
from models_library.api_schemas_invitations.invitations import (
    ApiEncryptedInvitation,
    ApiInvitationContent,
    ApiInvitationContentAndLink,
    ApiInvitationInputs,
)

from ..core.settings import ApplicationSettings
from ..services.invitations import (
    InvalidInvitationCodeError,
    create_invitation_link_and_content,
    extract_invitation_code_from_query,
    extract_invitation_content,
)
from ._dependencies import get_settings, get_validated_credentials

_logger = logging.getLogger(__name__)

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


router = APIRouter()


@router.post(
    "/invitations",
    response_model=ApiInvitationContentAndLink,
    response_model_by_alias=False,
)
async def create_invitation(
    invitation_inputs: ApiInvitationInputs,
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    _credentials: Annotated[
        HTTPBasicCredentials | None, Depends(get_validated_credentials)
    ],
):
    """Generates a new invitation code and returns its content and an invitation link"""

    invitation_link, invitation_content = create_invitation_link_and_content(
        invitation_inputs,
        secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_OSPARC_URL,
        default_product=settings.INVITATIONS_DEFAULT_PRODUCT,
    )
    invitation = ApiInvitationContentAndLink(
        **invitation_content.model_dump(),
        invitation_url=invitation_link,
    )

    _logger.info("New invitation: %s", f"{invitation.model_dump_json(indent=1)}")

    return invitation


@router.post(
    "/invitations:extract",
    response_model=ApiInvitationContent,
    response_model_by_alias=False,
)
async def extracts_invitation_from_code(
    encrypted: ApiEncryptedInvitation,
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    _credentials: Annotated[
        HTTPBasicCredentials | None, Depends(get_validated_credentials)
    ],
):
    """Decrypts the invitation code and returns its content"""

    try:
        invitation = extract_invitation_content(
            invitation_code=extract_invitation_code_from_query(
                encrypted.invitation_url
            ),
            secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
            default_product=settings.INVITATIONS_DEFAULT_PRODUCT,
        )
    except InvalidInvitationCodeError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=INVALID_INVITATION_URL_MSG,
        ) from err

    return invitation
