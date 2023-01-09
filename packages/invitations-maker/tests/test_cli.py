# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

from faker import Faker
from invitations_maker.cli import app
from typer.testing import CliRunner


def test_cli_help(cli_runner: CliRunner):
    result = cli_runner.invoke(app, "--help")
    assert result.exit_code == os.EX_OK


def test_invite_user(cli_runner: CliRunner, faker: Faker):
    result = cli_runner.invoke(app, "generate-key")
    assert result.exit_code == os.EX_OK

    # export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
    environs = dict(
        INVITATIONS_MAKER_SECRET_KEY=result.stdout.strip(),
        INVITATIONS_MAKER_OSPARC_URL=faker.url(),
    )

    result = cli_runner.invoke(app, f"invite {faker.email()} --issuer=ME", env=environs)
    assert result.exit_code == os.EX_OK
