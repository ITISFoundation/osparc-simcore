import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from ..core.settings import ApplicationSettings
from ..invitations import (
    InvalidInvitationCode,
    InvitationContent,
    InvitationInputs,
    create_invitation_link,
    extract_invitation_code_from,
    extract_invitation_content,
)
from ._dependencies import get_current_username, get_settings

logger = logging.getLogger(__name__)

INVALID_INVITATION_URL_MSG = "Invalid invitation link"

#
# API SCHEMA MODELS
#


_INPUTS_EXAMPLE: dict[str, Any] = {
    "issuer": "issuerid",
    "guest": "invitedguest@company.com",
    "trial_account_days": 2,
}


class _ApiInvitationInputs(InvitationInputs):
    class Config:
        schema_extra = {"example": _INPUTS_EXAMPLE}


class _ApiInvitationContent(InvitationContent):
    class Config:
        schema_extra = {
            "example": {
                **_INPUTS_EXAMPLE,
                "created": "2023-01-11 13:11:47.293595",
            }
        }


class _InvitationContentAndLink(_ApiInvitationContent):
    invitation_url: HttpUrl = Field(..., description="Invitation link")

    class Config:
        schema_extra = {
            "example": {
                **_INPUTS_EXAMPLE,
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
    settings: ApplicationSettings = Depends(get_settings),
    username: str = Depends(get_current_username),
):
    """Generates a new invitation code and returns its content and an invitation link"""
    assert username == settings.INVITATIONS_USERNAME  # nosec

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

    logger.info("New invitation: %s", f"{invitation.json(indent=1)}")

    return invitation


@router.post(
    "/invitations:extract",
    response_model=_ApiInvitationContent,
    response_model_by_alias=False,
)
async def extracts_invitation_from_code(
    encrypted: _EncryptedInvitation,
    settings: ApplicationSettings = Depends(get_settings),
    username: str = Depends(get_current_username),
):
    """Decrypts the invitation code and returns its content"""

    assert username == settings.INVITATIONS_USERNAME  # nosec

    try:
        invitation = extract_invitation_content(
            invitation_code=extract_invitation_code_from(encrypted.invitation_url),
            secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        )
    except InvalidInvitationCode as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=INVALID_INVITATION_URL_MSG,
        ) from err

    return invitation
