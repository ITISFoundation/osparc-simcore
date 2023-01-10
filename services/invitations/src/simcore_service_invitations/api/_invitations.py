import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from ..core.settings import WebApplicationSettings
from ..invitations import (
    InvalidInvitationCode,
    InvitationData,
    create_invitation_link,
    extract_invitation_data,
    parse_invitation_code,
)
from ._dependencies import get_current_username, get_settings

logger = logging.getLogger(__name__)


#
# API SCHEMA MODELS
#

INVALID_INVITATION_URL_MSG = "Invalid invitation link"


class InvitationCreate(InvitationData):
    class Config:
        # Same as InvitationData but WITHOUT alias
        schema_extra = {
            "example": {
                "issuer": "issuerid",
                "guest": "invitedguest@company.com",
                "trial_account_days": None,
            }
        }


class InvitationGet(InvitationCreate):
    invitation_url: HttpUrl = Field(..., description="Resulting invitation link")

    class Config:
        schema_extra = {
            "example": {
                "issuer": "issuerid",
                "guest": "invitedguest@company.com",
                "trial_account_days": None,
                "invitation_url": "https://foo.com/#/registration?invitation=1234",
            }
        }


class InvitationCheck(BaseModel):
    invitation_url: HttpUrl = Field(..., description="Full Invitation link")


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.post("/invitation", response_model=InvitationGet, response_model_by_alias=False)
async def create_invitation(
    invitation_create: InvitationCreate,
    settings: WebApplicationSettings = Depends(get_settings),
    username: str = Depends(get_current_username),
):
    """Generates a new invitation link"""
    assert username == settings.INVITATIONS_USERNAME  # nosec

    invitation_link = create_invitation_link(
        invitation_create,
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_MAKER_OSPARC_URL,
    )
    invitation = InvitationGet(
        invitation_url=invitation_link,
        **invitation_create.dict(),
    )

    logger.info("New invitation: %s", f"{invitation.json(indent=1)}")

    return invitation


@router.post(
    "/invitation:check", response_model=InvitationGet, response_model_by_alias=False
)
async def check_invitation(
    invitation_check: InvitationCheck,
    settings: WebApplicationSettings = Depends(get_settings),
    username: str = Depends(get_current_username),
):
    """Generates a new invitation link"""
    assert username == settings.INVITATIONS_USERNAME  # nosec

    try:
        invitation = extract_invitation_data(
            invitation_code=parse_invitation_code(invitation_check.invitation_url),
            secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value().encode(),
        )
    except InvalidInvitationCode as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=INVALID_INVITATION_URL_MSG,
        ) from err

    invitation = InvitationGet(
        invitation_url=invitation_check.invitation_url,
        **invitation.dict(),
    )

    return invitation
