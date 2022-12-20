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
