# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

import pytest
from faker import Faker
from models_library.products import ProductName
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import load_dotenv, setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_invitations._meta import API_VERSION
from simcore_service_invitations.cli import main
from simcore_service_invitations.core.settings import ApplicationSettings
from simcore_service_invitations.services.invitations import InvitationInputs
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    # invitations-maker --help
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_invite_user_and_check_invitation(
    cli_runner: CliRunner,
    faker: Faker,
    invitation_data: InvitationInputs,
    default_product: ProductName,
):
    # invitations-maker generate-key
    result = cli_runner.invoke(main, "generate-key")
    assert result.exit_code == os.EX_OK, result.output

    # export INVITATIONS_SECRET_KEY=$(invitations-maker generate-key)
    environs = {
        "INVITATIONS_SECRET_KEY": result.stdout.strip(),
        "INVITATIONS_OSPARC_URL": faker.url(),
        "INVITATIONS_DEFAULT_PRODUCT": default_product,
    }

    expected = {
        **invitation_data.model_dump(exclude={"product"}),
        "product": environs["INVITATIONS_DEFAULT_PRODUCT"],
    }

    # invitations-maker invite guest@email.com --issuer=me --trial-account-days=3
    trial_account = ""
    if invitation_data.trial_account_days:
        trial_account = f"--trial-account-days={invitation_data.trial_account_days}"

    result = cli_runner.invoke(
        main,
        f"invite {invitation_data.guest} --issuer={invitation_data.issuer} {trial_account}",
        env=environs,
    )
    assert result.exit_code == os.EX_OK, result.output

    # NOTE: for some reason, when running from CLI the outputs get folded!
    invitation_url = result.stdout.replace("\n", "")

    # invitations-maker extrac https://foo#invitation=123
    result = cli_runner.invoke(
        main,
        f'extract "{invitation_url}"',
        env=environs,
    )
    assert result.exit_code == os.EX_OK, result.output
    assert (
        expected
        == TypeAdapter(InvitationInputs).validate_json(result.stdout).model_dump()
    )


def test_echo_dotenv(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    # invitations-maker --echo-dotenv
    result = cli_runner.invoke(main, "echo-dotenv --auto-password")
    assert result.exit_code == os.EX_OK, result.output

    environs = load_dotenv(result.stdout)

    envs = setenvs_from_dict(monkeypatch, environs)
    settings_from_obj = ApplicationSettings.model_validate(envs)
    settings_from_envs = ApplicationSettings.create_from_envs()

    assert settings_from_envs == settings_from_obj


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    print(result.output)
    settings = ApplicationSettings.model_validate_json(result.output)
    assert settings == ApplicationSettings.create_from_envs()
