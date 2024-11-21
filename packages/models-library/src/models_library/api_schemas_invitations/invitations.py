from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ..invitations import InvitationContent, InvitationInputs
from ..products import ProductName

_INPUTS_EXAMPLE: dict[str, Any] = {
    "issuer": "issuerid",
    "guest": "invitedguest@company.com",
    "trial_account_days": 2,
}


class ApiInvitationInputs(InvitationInputs):
    model_config = ConfigDict(json_schema_extra={"example": _INPUTS_EXAMPLE})


class ApiInvitationContent(InvitationContent):

    product: ProductName = Field(
        ..., description="This invitations can only be used for this product."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **_INPUTS_EXAMPLE,
                "product": "osparc",
                "created": "2023-01-11 13:11:47.293595",
            }
        }
    )


class ApiInvitationContentAndLink(ApiInvitationContent):
    invitation_url: HttpUrl = Field(..., description="Invitation link")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **ApiInvitationContent.model_config["json_schema_extra"]["example"],  # type: ignore[index,dict-item]
                "invitation_url": "https://foo.com/#/registration?invitation=1234",
            }
        }
    )


class ApiEncryptedInvitation(BaseModel):
    invitation_url: HttpUrl = Field(..., description="Invitation link")
