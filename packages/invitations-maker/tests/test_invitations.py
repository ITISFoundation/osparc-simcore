# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from faker import Faker
from invitations_maker.invitations import InvitationData, create_invitation_link


def test_create_invitation(faker: Faker, secret_key: str):

    invitation_data = InvitationData(
        issuer="Invitations server", guest=faker.email(), trial_account_days=3
    )

    invitation_link = create_invitation_link(
        invitation_data, secret_key=secret_key.encode(), base_url=faker.url()
    )

    print(invitation_link)
