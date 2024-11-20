import base64
import binascii
import logging
from urllib import parse

from cryptography.fernet import Fernet, InvalidToken
from models_library.invitations import InvitationContent, InvitationInputs
from models_library.products import ProductName
from pydantic import ConfigDict, HttpUrl, TypeAdapter, ValidationError
from starlette.datastructures import URL

_logger = logging.getLogger(__name__)


def _to_initial(v: str):
    return v[0]


class InvalidInvitationCodeError(Exception):
    ...


class _ContentWithShortNames(InvitationContent):
    """Helper model to serialize/deserialize to json using shorter field names"""

    @classmethod
    def serialize(cls, model_obj: InvitationContent) -> str:
        """Exports to json using *short* aliases and values in order to produce shorter codes"""
        model_w_short_aliases_json: str = cls.model_construct(
            **model_obj.model_dump(exclude_unset=True)
        ).model_dump_json(exclude_unset=True, by_alias=True)
        # NOTE: json arguments try to minimize the amount of data
        # serialized. The CONS is that it relies on models in the code
        # that might change over time. This might lead to some datasets in codes
        # that fail in deserialization
        return model_w_short_aliases_json

    @classmethod
    def deserialize(cls, raw_json: str) -> InvitationContent:
        """Parses a json string and returns InvitationContent model"""
        model_w_short_aliases = cls.model_validate_json(raw_json)
        return InvitationContent.model_construct(
            **model_w_short_aliases.model_dump(exclude_unset=True)
        )

    model_config = ConfigDict(
        # NOTE: Can export with alias: short aliases to minimize the size of serialization artifact
        alias_generator=_to_initial,
        populate_by_name=True,  # NOTE: can parse using field names
        frozen=True,
        str_strip_whitespace=True,
    )


#
# Utils
#


def _build_link(
    base_url: str,
    code_url_safe: str,
) -> HttpUrl:
    r = URL("/registration").include_query_params(invitation=code_url_safe)

    # Adds query to fragment
    base_url = f"{base_url}/"
    url = URL(base_url).replace(fragment=f"{r}")
    return TypeAdapter(HttpUrl).validate_python(f"{url}")


def _fernet_encrypt_as_urlsafe_code(
    data: bytes,
    secret_key: bytes,
) -> bytes:
    fernet = Fernet(secret_key)
    code: bytes = fernet.encrypt(data)
    return base64.urlsafe_b64encode(code)


def _create_invitation_code(
    content: InvitationContent,
    secret_key: bytes,
) -> bytes:
    """Produces url-safe invitation code in bytes"""
    # shorten names
    content_jsonstr: str = _ContentWithShortNames.serialize(content)
    assert "\n" not in content_jsonstr  # nosec

    # encrypts contents
    return _fernet_encrypt_as_urlsafe_code(
        data=content_jsonstr.encode(),
        secret_key=secret_key,
    )


#
# API
#


def create_invitation_link_and_content(
    invitation_data: InvitationInputs,
    secret_key: bytes,
    base_url: HttpUrl,
    default_product: ProductName,
) -> tuple[HttpUrl, InvitationContent]:
    content = InvitationContent.create_from_inputs(invitation_data, default_product)
    code = _create_invitation_code(content, secret_key)
    # Adds message as the invitation in query
    link = _build_link(
        base_url=f"{base_url}",
        code_url_safe=code.decode(),
    )
    return link, content


def extract_invitation_code_from_query(invitation_url: HttpUrl) -> str:
    """Parses url and extracts invitation code from url's query"""
    if not invitation_url.fragment:
        raise InvalidInvitationCodeError

    try:
        query_params = dict(parse.parse_qsl(URL(invitation_url.fragment).query))
        invitation_code: str = query_params["invitation"]
        return invitation_code
    except KeyError as err:
        _logger.debug("Invalid invitation: %s", err)
        raise InvalidInvitationCodeError from err


def decrypt_invitation(
    invitation_code: str, secret_key: bytes, default_product: ProductName
) -> InvitationContent:
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
    content = _ContentWithShortNames.deserialize(raw_json=decryted.decode())
    if content.product is None:
        content.product = default_product
    return content


def extract_invitation_content(
    invitation_code: str, secret_key: bytes, default_product: ProductName
) -> InvitationContent:
    """As decrypt_invitation but raises InvalidInvitationCode if fails"""
    try:
        content = decrypt_invitation(
            invitation_code=invitation_code,
            secret_key=secret_key,
            default_product=default_product,
        )
        assert content.product is not None  # nosec
        return content

    except (InvalidToken, ValidationError, binascii.Error) as err:
        _logger.debug("Invalid code: %s", err)
        raise InvalidInvitationCodeError from err
