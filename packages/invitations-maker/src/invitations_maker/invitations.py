import base64
import binascii
from typing import Optional, cast

from cryptography.fernet import Fernet, InvalidToken
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    PositiveInt,
    ValidationError,
    parse_obj_as,
)
from starlette.datastructures import URL


class InvalidInvitationCode(Exception):
    ...


class InvitationData(BaseModel):
    """Data in an invitation"""

    issuer: str = Field(
        ...,
        description="Who issued this invitation? Some identifier such as LicenseRequestID",
        min_length=1,
        max_length=30,
    )
    guest: EmailStr = Field(
        ...,
        description="Invitee's email. Note that the registration can ONLY be used with this email",
    )
    trial_account_days: Optional[PositiveInt] = Field(
        None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
    )

    class Config:

        allow_population_by_field_name = True  # NOTE: can parse using field names
        allow_mutation = False
        anystr_strip_whitespace = True

        # NOTE: Can export with alias: short aliases to minimize the size of serialization artifact
        fields = {
            "issuer": {
                "alias": "i",
            },
            "guest": {
                "alias": "g",
            },
            "trial_account_days": {
                "alias": "t",
            },
        }


def _build_link(
    base_url: str,
    code_url_safe: str,
) -> HttpUrl:
    # TODO: test invitations url INVARIANT
    r = URL("/registration").include_query_params(invitation=code_url_safe)

    # Adds query to fragment
    base_url = f"{base_url.rstrip('/')}/"
    url = URL(base_url).replace(fragment=f"{r}")
    return cast(HttpUrl, parse_obj_as(HttpUrl, f"{url}"))


def _create_invitation_code(
    invitation_data: InvitationData, secret_key: bytes
) -> bytes:
    """Produces url-save  invitation code in bytes"""
    # creates message
    # NOTE: export using short aliasa and values in order to produce shorter messages
    serialized: str = invitation_data.json(exclude_unset=True, by_alias=True)

    # encrypts message
    fernet = Fernet(secret_key)
    code: bytes = fernet.encrypt(serialized.encode())
    return base64.urlsafe_b64encode(code)


def create_invitation_link(
    invitation_data: InvitationData, secret_key: bytes, base_url: HttpUrl
) -> HttpUrl:

    invitation_code = _create_invitation_code(
        invitation_data=invitation_data, secret_key=secret_key
    )
    # Adds message as the invitation in query
    url = _build_link(
        base_url=base_url,
        code_url_safe=invitation_code.decode(),
    )
    return url


def decrypt_invitation(invitation_code: str, secret_key: bytes) -> InvitationData:
    """

    raises cryptography.fernet.InvalidToken if code has a different secret_key (see test_invalid_invitation_secret)
    raises pydantic.ValidationError if sent invalid data (see test_invalid_invitation_data)
    raises binascii.Error if code is not fernet (binascii.Error))
    """
    # decode urlsafe (symmetric from base64.urlsafe_b64encode(encrypted))
    code: bytes = base64.urlsafe_b64decode(invitation_code)

    fernet = Fernet(secret_key)
    decryted: bytes = fernet.decrypt(token=code)

    # parses serialized invitation
    return InvitationData.parse_raw(decryted.decode())


def extract_invitation_data(invitation_code: str, secret_key: bytes) -> InvitationData:
    """As decrypt_invitation but raises InvalidInvitationCode if fails"""
    try:
        return decrypt_invitation(
            invitation_code=invitation_code, secret_key=secret_key
        )
    except (InvalidToken, ValidationError, binascii.Error) as err:
        raise InvalidInvitationCode from err
