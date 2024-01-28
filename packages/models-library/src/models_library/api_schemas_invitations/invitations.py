from typing import Any

from models_library.products import ProductName
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ..invitations import InvitationContent, InvitationInputs

_INPUTS_EXAMPLE: dict[str, Any] = {
    "issuer": "issuerid",
    "guest": "invitedguest@company.com",
    "trial_account_days": 2,
}


class ApiInvitationInputs(InvitationInputs):
    model_config = ConfigDict()


class ApiInvitationContent(InvitationContent):

    product: ProductName = Field(
        ..., description="This invitations can only be used for this product."
    )
    model_config = ConfigDict()


class ApiInvitationContentAndLink(ApiInvitationContent):
    invitation_url: HttpUrl = Field(..., description="Invitation link")
    model_config = ConfigDict()


class ApiEncryptedInvitation(BaseModel):
    invitation_url: HttpUrl = Field(..., description="Invitation link")
