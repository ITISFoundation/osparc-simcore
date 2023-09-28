from typing import Any, ClassVar

from pydantic import BaseModel, Field, HttpUrl

from ..invitations import InvitationContent, InvitationInputs

_INPUTS_EXAMPLE: dict[str, Any] = {
    "issuer": "issuerid",
    "guest": "invitedguest@company.com",
    "trial_account_days": 2,
}


class ApiInvitationInputs(InvitationInputs):
    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {"example": _INPUTS_EXAMPLE}


class ApiInvitationContent(InvitationContent):
    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **_INPUTS_EXAMPLE,
                "created": "2023-01-11 13:11:47.293595",
            }
        }


class ApiInvitationContentAndLink(ApiInvitationContent):
    invitation_url: HttpUrl = Field(..., description="Invitation link")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **_INPUTS_EXAMPLE,
                "created": "2023-01-11 12:11:47.293595",
                "invitation_url": "https://foo.com/#/registration?invitation=1234",
            }
        }


class ApiEncryptedInvitation(BaseModel):
    invitation_url: HttpUrl = Field(..., description="Invitation link")
