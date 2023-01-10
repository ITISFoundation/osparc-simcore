# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import os

from faker import Faker
from invitations_maker._meta import API_VERSION
from invitations_maker.cli import app
from invitations_maker.invitations import InvitationData
from invitations_maker.settings import WebApplicationSettings
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_dict
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    # invitations-maker --help
    result = cli_runner.invoke(app, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(app, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_invite_user_and_check_invitation(
    cli_runner: CliRunner, faker: Faker, invitation_data: InvitationData
):
    # invitations-maker generate-key
    result = cli_runner.invoke(app, "generate-key")
    assert result.exit_code == os.EX_OK, result.output

    # export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
    environs = dict(
        INVITATIONS_MAKER_SECRET_KEY=result.stdout.strip(),
        INVITATIONS_MAKER_OSPARC_URL=faker.url(),
    )

    # invitations-maker invite guest@email.com --issuer=me --trial-account-days=3
    trial_account = ""
    if invitation_data.trial_account_days:
        trial_account = f"--trial-account-days={invitation_data.trial_account_days}"

    result = cli_runner.invoke(
        app,
        f"invite {invitation_data.guest} --issuer={invitation_data.issuer} {trial_account}",
        env=environs,
    )
    assert result.exit_code == os.EX_OK, result.output

    invitation_url = result.stdout
    print(invitation_url)

    # invitations-maker check https://foo#invitation=123
    result = cli_runner.invoke(
        app,
        f"check {invitation_url}",
        env=environs,
    )
    assert result.exit_code == os.EX_OK, result.output
    assert invitation_data.dict() == json.loads(result.stdout)


def test_generate_dotenv(cli_runner: CliRunner, monkeypatch: MonkeyPatch):
    # invitations-maker --generate-dotenv
    result = cli_runner.invoke(app, "generate-dotenv --auto-password")
    assert result.exit_code == os.EX_OK, result.output

    environs = load_dotenv(result.stdout)

    envs = setenvs_from_dict(monkeypatch, environs)
    settings_from_obj = WebApplicationSettings.parse_obj(envs)
    settings_from_envs = WebApplicationSettings()

    assert settings_from_envs == settings_from_obj
