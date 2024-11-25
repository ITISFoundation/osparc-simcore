# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import binascii
from datetime import datetime, timezone
from typing import Counter
from urllib import parse

import cryptography.fernet
import pytest
from faker import Faker
from models_library.invitations import InvitationContent, InvitationInputs
from models_library.products import ProductName
from pydantic import BaseModel, ValidationError
from simcore_service_invitations.services.invitations import (
    InvalidInvitationCodeError,
    _ContentWithShortNames,
    _create_invitation_code,
    _fernet_encrypt_as_urlsafe_code,
    create_invitation_link_and_content,
    decrypt_invitation,
    extract_invitation_content,
)
from starlette.datastructures import URL


def test_all_invitation_fields_have_short_and_unique_aliases():
    # all have short alias
    all_alias = []
    for field in _ContentWithShortNames.model_fields.values():
        assert field.alias
        assert field.alias not in all_alias
        all_alias.append(field.alias)


def test_import_and_export_invitation_alias_by_alias(
    invitation_data: InvitationInputs,
):
    expected_content = InvitationContent(
        **invitation_data.model_dump(),
        created=datetime.now(tz=timezone.utc),
    )
    raw_data = _ContentWithShortNames.serialize(expected_content)

    got_content = _ContentWithShortNames.deserialize(raw_data)
    assert got_content == expected_content


def test_export_by_alias_produces_smaller_strings(
    invitation_data: InvitationInputs,
):
    content = InvitationContent(
        **invitation_data.model_dump(),
        created=datetime.now(tz=timezone.utc),
    )
    raw_data = _ContentWithShortNames.serialize(content)

    # export by alias produces smaller strings
    assert len(raw_data) < len(content.model_dump_json())


def test_create_and_decrypt_invitation(
    invitation_data: InvitationInputs,
    faker: Faker,
    secret_key: str,
    default_product: ProductName,
):
    invitation_link, _ = create_invitation_link_and_content(
        invitation_data,
        secret_key=secret_key.encode(),
        base_url=faker.url(),
        default_product=default_product,
    )
    assert URL(f"{invitation_link}").fragment
    query_params = dict(parse.parse_qsl(URL(URL(f"{invitation_link}").fragment).query))

    # will raise TokenError or ValidationError
    invitation = decrypt_invitation(
        invitation_code=query_params["invitation"],
        secret_key=secret_key.encode(),
        default_product=default_product,
    )

    assert isinstance(invitation, InvitationContent)
    assert invitation.product is not None

    expected = invitation_data.model_dump(exclude_none=True)
    expected.setdefault("product", default_product)
    assert invitation.model_dump(exclude={"created"}, exclude_none=True) == expected


#
# Tests errors raised for INVALID invitation codes
#


@pytest.fixture
def invitation_code(
    invitation_data: InvitationInputs, secret_key: str, default_product: ProductName
) -> str:
    content = InvitationContent.create_from_inputs(invitation_data, default_product)
    code = _create_invitation_code(content, secret_key.encode())
    return code.decode()


def test_valid_invitation_code(
    secret_key: str,
    invitation_code: str,
    invitation_data: InvitationInputs,
    default_product: ProductName,
):
    invitation = decrypt_invitation(
        invitation_code=invitation_code,
        secret_key=secret_key.encode(),
        default_product=default_product,
    )

    expected = invitation_data.model_dump(exclude_none=True)
    expected.setdefault("product", default_product)
    assert invitation.model_dump(exclude={"created"}, exclude_none=True) == expected


def test_invalid_invitation_encoding(
    secret_key: str,
    invitation_code: str,
    default_product: ProductName,
):
    my_invitation_code = invitation_code[:-1]  # strip last (wrong code!)
    my_secret_key = secret_key.encode()

    with pytest.raises(binascii.Error) as error_info:
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
            default_product=default_product,
        )

    assert f"{error_info.value}" == "Incorrect padding"

    with pytest.raises(InvalidInvitationCodeError):
        extract_invitation_content(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
            default_product=default_product,
        )


def test_invalid_invitation_secret(
    another_secret_key: str,
    invitation_code: str,
    default_product: ProductName,
):
    my_invitation_code = invitation_code
    my_secret_key = another_secret_key.encode()

    with pytest.raises(cryptography.fernet.InvalidToken):
        decrypt_invitation(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
            default_product=default_product,
        )

    with pytest.raises(InvalidInvitationCodeError):
        extract_invitation_content(
            invitation_code=my_invitation_code,
            secret_key=my_secret_key,
            default_product=default_product,
        )


def test_invalid_invitation_data(secret_key: str, default_product: ProductName):
    # encrypts contents
    class OtherModel(BaseModel):
        foo: int = 123

    secret = secret_key.encode()
    other_code = _fernet_encrypt_as_urlsafe_code(
        data=OtherModel().model_dump_json().encode(), secret_key=secret
    )

    with pytest.raises(ValidationError):
        decrypt_invitation(
            invitation_code=other_code.decode(),
            secret_key=secret,
            default_product=default_product,
        )

    with pytest.raises(InvalidInvitationCodeError):
        extract_invitation_content(
            invitation_code=other_code.decode(),
            secret_key=secret,
            default_product=default_product,
        )


def test_aliases_uniqueness():
    assert not [
        item
        for item, count in Counter(
            [field.alias for field in _ContentWithShortNames.model_fields.values()]
        ).items()
        if count > 1
    ]  # nosec
