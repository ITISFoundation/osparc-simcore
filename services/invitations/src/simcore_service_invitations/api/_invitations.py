import logging
from datetime import datetime
from typing import Annotated, Any, ClassVar

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel, Field, HttpUrl

from ..core.settings import ApplicationSettings
from ..invitations import (
    InvalidInvitationCodeError,
    InvitationContent,
    InvitationInputs,
    create_invitation_link,
    extract_invitation_code_from,
    extract_invitation_content,
)
from ._dependencies import get_settings, get_validated_credentials

_logger = logging.getLogger(__name__)

INVALID_INVITATION_URL_MSG = "Invalid invitation link"

#
# API SCHEMA MODELS
#


_MINIMAL_EXAMPLE: dict[str, Any] = {
    "issuer": "issuerid",
    "guest": "invitedguest@company.com",
}


_EXAMPLES: list[dict[str, Any]] = [
    _MINIMAL_EXAMPLE,
    {
        **_MINIMAL_EXAMPLE,
        "trial_account_days": 2,
    },
    {
        **_MINIMAL_EXAMPLE,
        "product": "s4llite",
    },
    {
        **_MINIMAL_EXAMPLE,
        "trial_account_days": 2,
        "product": "s4llite",
    },
]


class _ApiInvitationInputs(InvitationInputs):
    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": _MINIMAL_EXAMPLE,
            "examples": _EXAMPLES,
        }


class _ApiInvitationContent(InvitationContent):
    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **_MINIMAL_EXAMPLE,
                "created": "2023-01-11 13:11:47.293595",
            }
        }


class _InvitationContentAndLink(_ApiInvitationContent):
    invitation_url: HttpUrl = Field(..., description="Invitation link")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **_MINIMAL_EXAMPLE,
                "created": "2023-01-11 12:11:47.293595",
                "invitation_url": "https://foo.com/#/registration?invitation=1234",
            }
        }


class _EncryptedInvitation(BaseModel):
    invitation_url: HttpUrl = Field(..., description="Invitation link")


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.post(
    "/invitations",
    response_model=_InvitationContentAndLink,
    response_model_by_alias=False,
)
async def create_invitation(
    invitation_inputs: _ApiInvitationInputs,
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    _credentials: Annotated[
        HTTPBasicCredentials | None, Depends(get_validated_credentials)
    ],
):
    """Generates a new invitation code and returns its content and an invitation link"""

    invitation_link = create_invitation_link(
        invitation_inputs,
        secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_OSPARC_URL,
    )
    invitation = _InvitationContentAndLink(
        invitation_url=invitation_link,
        created=datetime.utcnow(),
        **invitation_inputs.dict(),
    )

    _logger.info("New invitation: %s", f"{invitation.json(indent=1)}")

    return invitation


@router.post(
    "/invitations:extract",
    response_model=_ApiInvitationContent,
    response_model_by_alias=False,
)
async def extracts_invitation_from_code(
    encrypted: _EncryptedInvitation,
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    _credentials: Annotated[
        HTTPBasicCredentials | None, Depends(get_validated_credentials)
    ],
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
