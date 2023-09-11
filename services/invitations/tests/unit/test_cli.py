# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

import pytest
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_dict
from simcore_service_invitations._meta import API_VERSION
from simcore_service_invitations.cli import app
from simcore_service_invitations.core.settings import ApplicationSettings
from simcore_service_invitations.invitations import InvitationInputs
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    # simcore-service-invitations --help
    result = cli_runner.invoke(app, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(app, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def _run_generate_and_get_dotenv(cli_runner: CliRunner) -> EnvVarsDict:
    # simcore-service-invitations --generate-dotenv
    result = cli_runner.invoke(app, "generate-dotenv --auto-password")
    assert result.exit_code == os.EX_OK, result.output
    return load_dotenv(result.stdout)


def test_generate_key(cli_runner: CliRunner):
    # simcore-service-invitations generate-key
    result = cli_runner.invoke(app, "generate-key")
    assert result.exit_code == os.EX_OK, result.output

    # export INVITATIONS_SECRET_KEY=$(simcore-service-invitations generate-key)
    INVITATIONS_SECRET_KEY = result.stdout.strip()
    assert len(INVITATIONS_SECRET_KEY) >= 44


def test_invite_user_and_check_invitation(
    cli_runner: CliRunner, faker: Faker, invitation_data: InvitationInputs
):
    environs = _run_generate_and_get_dotenv(cli_runner)

    # simcore-service-invitations invite guest@email.com --issuer=me --trial-account-days=3
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

    # simcore-service-invitations extrac https://foo#invitation=123
    result = cli_runner.invoke(
        app,
        f"extract {invitation_url}",
        env=environs,
    )
    assert result.exit_code == os.EX_OK, result.output
    assert invitation_data == InvitationInputs.parse_raw(result.stdout)


def test_generate_dotenv(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    # simcore-service-invitations --generate-dotenv
    environs = _run_generate_and_get_dotenv(cli_runner)

    envs = setenvs_from_dict(monkeypatch, environs)
    settings_from_obj = ApplicationSettings.parse_obj(envs)
    settings_from_envs = ApplicationSettings()

    assert settings_from_envs == settings_from_obj


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(app, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    print(result.output)
    settings = ApplicationSettings.parse_raw(result.output)
    assert settings == ApplicationSettings.create_from_envs()
