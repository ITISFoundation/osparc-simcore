# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import os

from faker import Faker
from invitations_maker.cli import app
from invitations_maker.invitations import InvitationData
from typer.testing import CliRunner


def test_cli_help(cli_runner: CliRunner):
    # invitations-maker --help
    result = cli_runner.invoke(app, "--help")
    assert result.exit_code == os.EX_OK


def test_invite_user_and_check_invitation(
    cli_runner: CliRunner, faker: Faker, invitation_data: InvitationData
):
    # invitations-maker generate-key
    result = cli_runner.invoke(app, "generate-key")
    assert result.exit_code == os.EX_OK

    # export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
    environs = dict(
        INVITATIONS_MAKER_SECRET_KEY=result.stdout.strip(),
        INVITATIONS_MAKER_OSPARC_URL=faker.url(),
    )

    # invitations-maker invite guest@email.com --issuer=ME
    trial_account = ""
    if invitation_data.trial_account_days:
        trial_account = f"--trial-account-days={invitation_data.trial_account_days}"

    result = cli_runner.invoke(
        app,
        f"invite {invitation_data.guest} --issuer={invitation_data.issuer} {trial_account}",
        env=environs,
    )
    assert result.exit_code == os.EX_OK

    invitation_url = result.stdout
    print(invitation_url)

    # invitations-maker check https://foo
    result = cli_runner.invoke(
        app,
        f"check {invitation_url}",
        env=environs,
    )
    assert result.exit_code == os.EX_OK
    assert invitation_data.dict() == json.loads(result.stdout.replace("'", '"').strip())
