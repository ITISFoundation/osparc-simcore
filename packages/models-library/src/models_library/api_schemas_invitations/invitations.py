from typing import Any, ClassVar

from models_library.products import ProductName
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

    product: ProductName = Field(
        ..., description="This invitations can only be used for this product."
    )

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **_INPUTS_EXAMPLE,
                "product": "osparc",
                "created": "2023-01-11 13:11:47.293595",
            }
        }


class ApiInvitationContentAndLink(ApiInvitationContent):
    invitation_url: HttpUrl = Field(..., description="Invitation link")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                **ApiInvitationContent.Config.schema_extra["example"],
                "invitation_url": "https://foo.com/#/registration?invitation=1234",
            }
        }


class ApiEncryptedInvitation(BaseModel):
    invitation_url: HttpUrl = Field(..., description="Invitation link")
