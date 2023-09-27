import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasicCredentials
from models_library.api_schemas_invitations.invitations import (
    ApiEncryptedInvitation,
    ApiInvitationContent,
    ApiInvitationContentAndLink,
    ApiInvitationInputs,
)

from ..core.settings import ApplicationSettings
from ..invitations import (
    InvalidInvitationCodeError,
    create_invitation_link,
    extract_invitation_code_from,
    extract_invitation_content,
)
from ._dependencies import get_settings, get_validated_credentials

_logger = logging.getLogger(__name__)

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.post(
    "/invitations",
    response_model=ApiInvitationContentAndLink,
    response_model_by_alias=False,
)
async def create_invitation(
    invitation_inputs: ApiInvitationInputs,
    settings: ApplicationSettings = Depends(get_settings),
    _credentials: HTTPBasicCredentials | None = Depends(get_validated_credentials),
):
    """Generates a new invitation code and returns its content and an invitation link"""

    invitation_link = create_invitation_link(
        invitation_inputs,
        secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_OSPARC_URL,
    )
    invitation = ApiInvitationContentAndLink(
        invitation_url=invitation_link,
        created=datetime.now(tz=timezone.utc),
        **invitation_inputs.dict(),
    )

    _logger.info("New invitation: %s", f"{invitation.json(indent=1)}")

    return invitation


@router.post(
    "/invitations:extract",
    response_model=ApiInvitationContent,
    response_model_by_alias=False,
)
async def extracts_invitation_from_code(
    encrypted: ApiEncryptedInvitation,
    settings: ApplicationSettings = Depends(get_settings),
    _credentials: HTTPBasicCredentials | None = Depends(get_validated_credentials),
):
    """Decrypts the invitation code and returns its content"""

    try:
        invitation = extract_invitation_content(
            invitation_code=extract_invitation_code_from(encrypted.invitation_url),
            secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        )
    except InvalidInvitationCodeError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=INVALID_INVITATION_URL_MSG,
        ) from err

    return invitation
