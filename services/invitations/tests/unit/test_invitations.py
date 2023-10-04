# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import binascii
from datetime import datetime, timezone
from urllib import parse

import cryptography.fernet
import pytest
from faker import Faker
from models_library.invitations import InvitationContent, InvitationInputs
from pydantic import BaseModel, ValidationError
from simcore_service_invitations.invitations import (
    InvalidInvitationCodeError,
    _ContentWithShortNames,
    _create_invitation_code,
    _fernet_encrypt_as_urlsafe_code,
    create_invitation_link,
    decrypt_invitation,
    extract_invitation_content,
)
from starlette.datastructures import URL


def test_all_invitation_fields_have_short_and_unique_aliases():
    # all have short alias
    all_alias = []
    for field in _ContentWithShortNames.__fields__.values():
        assert field.alias
        assert field.alias not in all_alias
        all_alias.append(field.alias)


def test_import_and_export_invitation_alias_by_alias(
    invitation_data: InvitationInputs,
):
    expected_content = InvitationContent(
        **invitation_data.dict(),
        created=datetime.now(tz=timezone.utc),
    )
    raw_data = _ContentWithShortNames.serialize(expected_content)

    got_content = _ContentWithShortNames.deserialize(raw_data)
    assert got_content == expected_content


def test_export_by_alias_produces_smaller_strings(
    invitation_data: InvitationInputs,
):
    content = InvitationContent(
        **invitation_data.dict(),
        created=datetime.now(tz=timezone.utc),
    )
    raw_data = _ContentWithShortNames.serialize(content)

    # export by alias produces smaller strings
    assert len(raw_data) < len(content.json())


def test_create_and_decrypt_invitation(
    invitation_data: InvitationInputs, faker: Faker, secret_key: str
):
    invitation_link = create_invitation_link(
        invitation_data, secret_key=secret_key.encode(), base_url=faker.url()
    )

    print(invitation_link)

    query_params = dict(parse.parse_qsl(URL(invitation_link.fragment).query))

    # will raise TokenError or ValidationError
    invitation = decrypt_invitation(
        invitation_code=query_params["invitation"],
        secret_key=secret_key.encode(),
    )

    assert isinstance(invitation, InvitationContent)
    assert invitation.dict(exclude={"created"}) == invitation_data.dict()


#
# Tests errors raised for INVALID invitation codes
#


@pytest.fixture
def invitation_code(invitation_data: InvitationInputs, secret_key: str) -> str:
    return _create_invitation_code(
        invitation_data, secret_key=secret_key.encode()
    ).decode()


def test_valid_invitation_code(
    secret_key: str,
    invitation_code: str,
    invitation_data: InvitationInputs,
):
    invitation = decrypt_invitation(
        invitation_code=invitation_code,
        secret_key=secret_key.encode(),
    )

    assert invitation.dict(exclude={"created"}) == invitation_data.dict()


def test_invalid_invitation_encoding(secret_key: str, invitation_code: str):
    my_invitation_code = invitation_code[:-1]  # strip last (wrong code!)
    my_secret_key = secret_key.encode()

    with pytest.raises(binascii.Error) as error_info:
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )

    assert f"{error_info.value}" == "Incorrect padding"

    with pytest.raises(InvalidInvitationCodeError):
        extract_invitation_content(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )


def test_invalid_invitation_secret(another_secret_key: str, invitation_code: str):
    my_invitation_code = invitation_code
    my_secret_key = another_secret_key.encode()

    with pytest.raises(cryptography.fernet.InvalidToken):
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )

    with pytest.raises(InvalidInvitationCodeError):
        extract_invitation_content(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )


def test_invalid_invitation_data(secret_key: str):
    # encrypts contents
    class OtherData(BaseModel):
        foo: int = 123

    my_secret_key = secret_key.encode()
    my_invitation_code = _fernet_encrypt_as_urlsafe_code(
        data=OtherData().json().encode(), secret_key=my_secret_key
    )

    with pytest.raises(ValidationError):
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )

    with pytest.raises(InvalidInvitationCodeError):
        extract_invitation_content(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )
