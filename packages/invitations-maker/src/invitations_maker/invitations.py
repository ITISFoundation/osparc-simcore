import base64
from typing import Optional

from cryptography.fernet import Fernet
from pydantic import BaseModel, EmailStr, Field, HttpUrl, PositiveInt, parse_obj_as
from starlette.datastructures import URL


class InvitationData(BaseModel):
    issuer: str = Field(
        ...,
        description="Who issued this invitation? Some identifier such as LicenseRequestID",
        max_length=10,
        alias="i",
    )
    guest: Optional[EmailStr] = Field(
        ...,
        description="Invitee's email or None if invitation is not locked to an email",
        alias="g",
    )
    trial_account_days: Optional[PositiveInt] = Field(
        None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
        alias="t",
    )

    class Config:
        allow_population_by_field_name = True
        anystr_strip_whitespace = True
        allow_mutation = False


def _build_link(
    base_url: str,
    code_url_safe: str,
):
    # TODO: test invitations url INVARIANT
    r = URL("/registration").include_query_params(invitation=code_url_safe)

    # Adds query to fragment
    base_url = f"{base_url.rstrip('/')}/"
    url = URL(base_url).replace(fragment=f"{r}")
    return parse_obj_as(HttpUrl, f"{url}")


def create_invitation_link(
    invitation_data: InvitationData, secret_key: bytes, base_url: HttpUrl
) -> HttpUrl:

    # creates message
    # NOTE: alias are very short and values are limited in lenght to produce a shorter code
    message: str = invitation_data.json(exclude_unset=True, by_alias=True)

    # encrypts message
    fernet = Fernet(secret_key)
    encrypted: bytes = fernet.encrypt(message.encode())

    # Adds message as the invitation in query
    url = _build_link(
        base_url=base_url,
        code_url_safe=base64.urlsafe_b64encode(encrypted).decode(),
    )
    return url


def decrypt_invitation(invitation_code: str, secret_key: bytes) -> InvitationData:
    # decode urlsafe (symmetric from base64.urlsafe_b64encode(encrypted))
    code: bytes = base64.urlsafe_b64decode(invitation_code)

    fernet = Fernet(secret_key)
    decryted: bytes = fernet.decrypt(token=code)

    # parse
    return InvitationData.parse_raw(decryted.decode())
