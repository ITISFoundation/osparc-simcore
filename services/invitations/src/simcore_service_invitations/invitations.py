import base64
import binascii
import logging
from datetime import datetime
from typing import Optional, cast
from urllib import parse

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

logger = logging.getLogger(__name__)

#
# Errors
#


class InvalidInvitationCode(Exception):
    ...


#
# Models
#


class InvitationInputs(BaseModel):
    """Input data necessary to create an invitation"""

    issuer: str = Field(
        ...,
        description="Identifies who issued the invitation. E.g. an email, a service name etc",
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


class InvitationContent(InvitationInputs):
    """Data in an invitation"""

    created: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp for creation"
    )

    def as_invitation_inputs(self) -> InvitationInputs:
        return self.copy(exclude={"created"})

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
            "created": {
                "alias": "c",
            },
        }


#
# Utils
#


def _build_link(
    base_url: str,
    code_url_safe: str,
) -> HttpUrl:
    r = URL("/registration").include_query_params(invitation=code_url_safe)

    # Adds query to fragment
    base_url = f"{base_url.rstrip('/')}/"
    url = URL(base_url).replace(fragment=f"{r}")
    return cast(HttpUrl, parse_obj_as(HttpUrl, f"{url}"))


def extract_invitation_code_from(invitation_url: HttpUrl) -> str:
    """Parses url and extracts invitation"""
    try:
        query_params = dict(parse.parse_qsl(URL(invitation_url.fragment).query))
        invitation_code: str = query_params["invitation"]
        return invitation_code
    except KeyError as err:
        logger.debug("Invalid invitation: %s", err)
        raise InvalidInvitationCode from err


def _fernet_encrypt_as_urlsafe_code(
    data: bytes,
    secret_key: bytes,
) -> bytes:
    fernet = Fernet(secret_key)
    code: bytes = fernet.encrypt(data)
    return base64.urlsafe_b64encode(code)


def _create_invitation_code(
    invitation_data: InvitationInputs, secret_key: bytes
) -> bytes:
    """Produces url-safe invitation code in bytes"""

    # builds content
    content = InvitationContent(
        **invitation_data.dict(),
        created=datetime.utcnow(),
    )

    # NOTE: export using short aliases and values in order to produce shorter messages
    content_jsonstr: str = content.json(exclude_unset=True, by_alias=True)
    assert "\n" not in content_jsonstr  # nosec

    # encrypts contents
    return _fernet_encrypt_as_urlsafe_code(
        data=content_jsonstr.encode(),
        secret_key=secret_key,
    )


#
# API
#


def create_invitation_link(
    invitation_data: InvitationInputs, secret_key: bytes, base_url: HttpUrl
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


def decrypt_invitation(invitation_code: str, secret_key: bytes) -> InvitationContent:
    """

    WARNING: invitation_code should not be taken directly from the url fragment without 'parse_invitation_code'

    raises cryptography.fernet.InvalidToken if code has a different secret_key (see test_invalid_invitation_secret)
    raises pydantic.ValidationError if sent invalid data (see test_invalid_invitation_data)
    raises binascii.Error if code is not fernet (binascii.Error))
    """
    # decode urlsafe (symmetric from base64.urlsafe_b64encode(encrypted))
    code: bytes = base64.urlsafe_b64decode(invitation_code)

    fernet = Fernet(secret_key)
    decryted: bytes = fernet.decrypt(token=code)

    # parses serialized invitation
    return InvitationContent.parse_raw(decryted.decode())


def extract_invitation_content(
    invitation_code: str, secret_key: bytes
) -> InvitationContent:
    """As decrypt_invitation but raises InvalidInvitationCode if fails"""
    try:
        return decrypt_invitation(
            invitation_code=invitation_code, secret_key=secret_key
        )
    except (InvalidToken, ValidationError, binascii.Error) as err:
        logger.debug("Invalid code: %s", err)
        raise InvalidInvitationCode from err
