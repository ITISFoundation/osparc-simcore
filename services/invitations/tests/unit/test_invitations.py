# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import binascii
from urllib import parse

import cryptography.fernet
import pytest
from faker import Faker
from pydantic import BaseModel, ValidationError
from simcore_service_invitations.invitations import (
    InvalidInvitationCode,
    InvitationData,
    _create_invitation_code,
    create_invitation_link,
    decrypt_invitation,
    extract_invitation_data,
)
from starlette.datastructures import URL


def test_import_and_export_invitation_alias_by_alias(invitation_data: InvitationData):

    # export by alias
    data_w_alias = invitation_data.dict(by_alias=True)

    # parse/import by alias
    invitation_data2 = InvitationData.parse_obj(data_w_alias)
    assert invitation_data == invitation_data2

    # export by alias produces smaller strings
    assert len(invitation_data.json(by_alias=True)) < len(
        invitation_data.json(by_alias=False)
    )


def test_create_and_decrypt_invitation(
    invitation_data: InvitationData, faker: Faker, secret_key: str
):

    invitation_link = create_invitation_link(
        invitation_data, secret_key=secret_key.encode(), base_url=faker.url()
    )

    print(invitation_link)

    query_params = dict(parse.parse_qsl(URL(invitation_link.fragment).query))

    # will raise TokenError or ValidationError
    received_invitation_data = decrypt_invitation(
        invitation_code=query_params["invitation"],
        secret_key=secret_key.encode(),
    )

    assert received_invitation_data == invitation_data


@pytest.fixture
def invitation_code(invitation_data: InvitationData, secret_key: str) -> str:
    return _create_invitation_code(
        invitation_data, secret_key=secret_key.encode()
    ).decode()


#
# Tests errors raised for INVALID invitation codes
#


def test_valid_invitation_code(
    secret_key: str,
    invitation_code: str,
    invitation_data: InvitationData,
):
    decrypted_invitation_data = decrypt_invitation(
        invitation_code=invitation_code,
        secret_key=secret_key.encode(),
    )

    assert decrypted_invitation_data == invitation_data


def test_invalid_invitation_encoding(secret_key: str, invitation_code: str):
    my_invitation_code = invitation_code[:-1]  # strip last (wrong code!)
    my_secret_key = secret_key.encode()

    with pytest.raises(binascii.Error) as error_info:
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )

    assert f"{error_info.value}" == "Incorrect padding"

    with pytest.raises(InvalidInvitationCode):
        extract_invitation_data(
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

    with pytest.raises(InvalidInvitationCode):
        extract_invitation_data(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )


def test_invalid_invitation_data(secret_key: str):
    class OtherData(BaseModel):
        foo: int = 123

    my_invitation_code = _create_invitation_code(
        invitation_data=OtherData(), secret_key=secret_key.encode()
    ).decode()
    my_secret_key = secret_key.encode()

    with pytest.raises(ValidationError):
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )

    with pytest.raises(InvalidInvitationCode):
        extract_invitation_data(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
        )
