import base64
from typing import Any, Optional

from cryptography.fernet import Fernet
from pydantic import BaseModel, EmailStr, Field, HttpUrl, PositiveInt, parse_obj_as
from starlette.datastructures import URL


class InvitationData(BaseModel):
    version: int = 1
    issuer: str = Field(..., description="Who issued this invitation?")
    guest: Optional[EmailStr] = Field(
        ...,
        description="Invitee's email or None if invitation is not locked to an email",
    )
    trial_account_days: Optional[PositiveInt] = Field(
        None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
    )

    def short_dict(self, **kwargs) -> dict[str, Any]:
        data = self.dict(**kwargs)
        return {key[:2]: value for key, value in data.items()}


def create_invitation_link(
    invitation_data: InvitationData, secret_key: bytes, base_url: HttpUrl
) -> HttpUrl:

    # creates message
    message: str = invitation_data.json(exclude_unset=True)

    # encrypts message
    fernet = Fernet(secret_key)
    encrypted: bytes = fernet.encrypt(message.encode())
    encrypted_url_safe: str = base64.urlsafe_b64encode(encrypted).decode()

    # TODO: test invitations url INVARIANT
    # Adds message as the invitation in query
    r = URL("/registration").include_query_params(invitation=encrypted_url_safe)
    # Adds query to fragment
    url = URL(base_url).replace(fragment=f"{r}")
    return parse_obj_as(HttpUrl, f"{url}")
