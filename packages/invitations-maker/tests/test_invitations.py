# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from urllib import parse

from faker import Faker
from invitations_maker.invitations import (
    InvitationData,
    create_invitation_link,
    decrypt_invitation,
)
from starlette.datastructures import URL


def test_create_invitation(faker: Faker, secret_key: str):

    invitation_data = InvitationData(
        issuer="Test", guest=faker.email(), trial_account_days=3
    )

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

    # TODO: tests error handling


def test_invitation_import_and_export_by_alias(faker: Faker):

    data = dict(
        issuer="Test",
        guest=faker.email(),
        trial_account_days=faker.random_int(min=1, max=100),
    )
    invitation_data = InvitationData.parse_obj(data)

    # export by alias
    data_w_alias = invitation_data.dict(by_alias=True)

    # parse/import by alias
    invitation_data2 = InvitationData.parse_obj(data_w_alias)
    assert invitation_data == invitation_data2

    # export by alias produces smaller strings
    assert len(invitation_data.json(by_alias=True)) < len(
        invitation_data.json(by_alias=False)
    )
