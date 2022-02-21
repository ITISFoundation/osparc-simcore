# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
from io import StringIO
from typing import Any, Dict, Type

import pytest
import typer
from dotenv import dotenv_values
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_as_envfile
from settings_library.base import BaseCustomSettings
from settings_library.utils_cli import create_settings_command
from typer.testing import CliRunner

log = logging.getLogger(__name__)

# HELPERS  --------------------------------------------------------------------------------


def envs_to_kwargs(envs: EnvVarsDict) -> Dict[str, Any]:
    kwargs = {}
    for k, v in envs.items():
        if v is not None:
            try:
                kwargs[k] = json.loads(v)
            except json.JSONDecodeError:
                kwargs[k] = v
    return kwargs


# FIXTURES --------------------------------------------------------------------------------


@pytest.fixture
def cli(fake_settings_class: Type[BaseCustomSettings]) -> typer.Typer:
    main = typer.Typer(name="app")

    @main.command()
    def run():
        """Emulates run"""
        typer.secho("Starting app ... ")
        typer.secho("Resolving settings ...", nl=False)
        typer.secho("DONE", fg=typer.colors.GREEN)

    # adds settings command
    settings_cmd = create_settings_command(fake_settings_class, log)
    main.command()(settings_cmd)

    return main


@pytest.fixture
def fake_granular_env_file_content() -> str:
    return """
        APP_HOST=localhost
        APP_PORT=80
        POSTGRES_HOST=localhost
        POSTGRES_PORT=5432
        POSTGRES_USER=foo
        POSTGRES_PASSWORD=secret
        POSTGRES_DB=foodb
        POSTGRES_MINSIZE=1
        POSTGRES_MAXSIZE=50
        POSTGRES_CLIENT_NAME=None
        MODULE_VALUE=10
    """


# TESTS -----------------------------------------------------------------------------------


def test_compose_commands(cli: typer.Typer, cli_runner: CliRunner):
    # NOTE: this tests is mostly here to raise awareness about what options
    # are exposed in the CLI so we can add tests if there is any update
    #
    result = cli_runner.invoke(cli, ["--help"], catch_exceptions=False)
    print(result.stdout)
    assert result.exit_code == 0, result

    # first command
    result = cli_runner.invoke(cli, ["run", "--help"], catch_exceptions=False)
    print(result.stdout)
    assert result.exit_code == 0, result

    # settings command
    result = cli_runner.invoke(cli, ["settings", "--help"], catch_exceptions=False)
    print(result.stdout)

    assert "--compact" in result.stdout
    assert result.exit_code == 0, result

    def extract_lines(text):
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines

    assert extract_lines(HELP) == extract_lines(result.stdout)


HELP = """
Usage: app settings [OPTIONS]

  Resolves settings and prints envfile

Options:
  --as-json / --no-as-json        [default: no-as-json]
  --as-json-schema / --no-as-json-schema
                                  [default: no-as-json-schema]
  --compact / --no-compact        Print compact form  [default: no-compact]
  --verbose / --no-verbose        [default: no-verbose]
  --show-secrets / --no-show-secrets
                                  [default: no-show-secrets]
  --exclude-unset / --no-exclude-unset
                                  displays settings that were explicitly setThis
                                  represents current config (i.e. required+
                                  defaults overriden).  [default: no-exclude-
                                  unset]
  --help                          Show this message and exit.
"""


def test_settings_as_json(
    cli: typer.Typer,
    fake_settings_class: Type[BaseCustomSettings],
    mock_environment,
    cli_runner: CliRunner,
):

    result = cli_runner.invoke(cli, ["settings", "--as-json"], catch_exceptions=False)
    print(result.stdout)

    # reuse resulting json to build settings
    settings: Dict = json.loads(result.stdout)
    assert fake_settings_class.parse_obj(settings)


def test_settings_as_json_schema(
    cli: typer.Typer,
    fake_settings_class: Type[BaseCustomSettings],
    mock_environment,
    cli_runner: CliRunner,
):

    result = cli_runner.invoke(
        cli, ["settings", "--as-json-schema"], catch_exceptions=False
    )
    print(result.stdout)

    # reuse resulting json to build settings
    settings_schema: Dict = json.loads(result.stdout)


def test_cli_default_settings_envs(
    cli: typer.Typer,
    fake_settings_class: Type[BaseCustomSettings],
    fake_granular_env_file_content: str,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    with monkeypatch.context() as patch:
        mocked_envs_1: EnvVarsDict = setenvs_as_envfile(
            patch, fake_granular_env_file_content
        )

        cli_settings_output = cli_runner.invoke(
            cli,
            ["settings", "--show-secrets"],
            catch_exceptions=False,
        ).stdout

    # now let's use these as env vars
    print(cli_settings_output)

    with monkeypatch.context() as patch:
        mocked_envs_2: EnvVarsDict = setenvs_as_envfile(
            patch,
            cli_settings_output,
        )
        settings_object = fake_settings_class()
        assert settings_object

        # NOTE: SEE BaseCustomSettings.Config.json_encoder for SecretStr
        settings_dict_wo_secrets = json.loads(settings_object.json(indent=2))
        assert settings_dict_wo_secrets == {
            "APP_HOST": "localhost",
            "APP_PORT": 80,
            "APP_OPTIONAL_ADDON": {"MODULE_VALUE": 10, "MODULE_VALUE_DEFAULT": 42},
            "APP_REQUIRED_PLUGIN": {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_PORT": 5432,
                "POSTGRES_USER": "foo",
                "POSTGRES_PASSWORD": "secret",
                "POSTGRES_DB": "foodb",
                "POSTGRES_MINSIZE": 1,
                "POSTGRES_MAXSIZE": 50,
                "POSTGRES_CLIENT_NAME": None,
            },
        }


def test_cli_compact_settings_envs(
    cli: typer.Typer,
    fake_settings_class: Type[BaseCustomSettings],
    fake_granular_env_file_content: str,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):

    with monkeypatch.context() as patch:
        mocked_envs_1: EnvVarsDict = setenvs_as_envfile(
            patch, fake_granular_env_file_content
        )

        settings_1 = fake_settings_class()

        # NOTE: SEE BaseCustomSettings.Config.json_encoder for SecretStr
        settings_1_dict_wo_secrets = json.loads(settings_1.json(indent=2))
        assert settings_1_dict_wo_secrets == {
            "APP_HOST": "localhost",
            "APP_PORT": 80,
            "APP_OPTIONAL_ADDON": {"MODULE_VALUE": 10, "MODULE_VALUE_DEFAULT": 42},
            "APP_REQUIRED_PLUGIN": {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_PORT": 5432,
                "POSTGRES_USER": "foo",
                "POSTGRES_PASSWORD": "secret",
                "POSTGRES_DB": "foodb",
                "POSTGRES_MINSIZE": 1,
                "POSTGRES_MAXSIZE": 50,
                "POSTGRES_CLIENT_NAME": None,
            },
        }

        setting_env_content_compact = cli_runner.invoke(
            cli,
            ["settings", "--compact"],
            catch_exceptions=False,
        ).stdout

    # now we use these as env vars
    print(setting_env_content_compact)

    with monkeypatch.context() as patch:
        mocked_envs_2: EnvVarsDict = setenvs_as_envfile(
            patch,
            setting_env_content_compact,
        )

        assert mocked_envs_2 == {
            "APP_HOST": "localhost",
            "APP_PORT": "80",
            "APP_OPTIONAL_ADDON": '{"MODULE_VALUE": 10, "MODULE_VALUE_DEFAULT": 42}',
            "APP_REQUIRED_PLUGIN": '{"POSTGRES_HOST": "localhost", "POSTGRES_PORT": 5432, "POSTGRES_USER": "foo", "POSTGRES_PASSWORD": "secret", "POSTGRES_DB": "foodb", "POSTGRES_MINSIZE": 1, "POSTGRES_MAXSIZE": 50, "POSTGRES_CLIENT_NAME": null}',
        }

        settings_2 = fake_settings_class()
        assert settings_1 == settings_2


def test_compact_format(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings_class: Type[BaseCustomSettings],
):
    compact_envs: EnvVarsDict = setenvs_as_envfile(
        monkeypatch,
        """
        APP_HOST=localhost
        APP_PORT=80
        APP_OPTIONAL_ADDON='{"MODULE_VALUE": 10, "MODULE_VALUE_DEFAULT": 42}'
        APP_REQUIRED_PLUGIN='{"POSTGRES_HOST": "localhost", "POSTGRES_PORT": 5432, "POSTGRES_USER": "foo", "POSTGRES_PASSWORD": "secret", "POSTGRES_DB": "foodb", "POSTGRES_MINSIZE": 1, "POSTGRES_MAXSIZE": 50, "POSTGRES_CLIENT_NAME": "None"}'
        """,
    )

    settings_from_envs1 = fake_settings_class()
    settings_from_init = fake_settings_class(**envs_to_kwargs(compact_envs))

    assert settings_from_envs1 == settings_from_init


def test_granular_format(
    monkeypatch: pytest.MonkeyPatch,
    fake_settings_class: Type[BaseCustomSettings],
):
    setenvs_as_envfile(
        monkeypatch,
        """
    APP_HOST=localhost
    APP_PORT=80

    # --- APP_OPTIONAL_ADDON ---
    MODULE_VALUE=10
    MODULE_VALUE_DEFAULT=42

    # --- APP_REQUIRED_PLUGIN ---
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_USER=foo
    POSTGRES_PASSWORD=secret
    # Database name
    POSTGRES_DB=foodb
    # Minimum number of connections in the pool
    POSTGRES_MINSIZE=1
    # Maximum number of connections in the pool
    POSTGRES_MAXSIZE=50
    # Name of the application connecting the postgres database, will default to use the host hostname (hostname on linux)
    POSTGRES_CLIENT_NAME=None
    """,
    )

    settings_from_envs = fake_settings_class()

    assert settings_from_envs == fake_settings_class(
        APP_HOST="localhost",
        APP_PORT=80,
        APP_OPTIONAL_ADDON={"MODULE_VALUE": 10, "MODULE_VALUE_DEFAULT": 42},
        APP_REQUIRED_PLUGIN={
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": 5432,
            "POSTGRES_USER": "foo",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_DB": "foodb",
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_CLIENT_NAME": None,
        },
    )


def test_cli_settings_exclude_unset(
    cli: typer.Typer,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    with monkeypatch.context() as patch:
        # minimal envfile
        mocked_envs: EnvVarsDict = setenvs_as_envfile(
            patch,
            """
            # these are required
            APP_HOST=localhost
            APP_PORT=80

            # --- APP_REQUIRED_PLUGIN ---
            # these are required
            POSTGRES_HOST=localhost
            POSTGRES_PORT=5432
            POSTGRES_USER=foo
            POSTGRES_PASSWORD=secret
            POSTGRES_DB=foodb

            # this is optional but set
            POSTGRES_MAXSIZE=20
            """,
        )

        # using exclude-unset
        stdout_as_envfile = cli_runner.invoke(
            cli,
            ["settings", "--show-secrets", "--exclude-unset"],
            catch_exceptions=False,
        ).stdout
        print(stdout_as_envfile)

        # parsing output as an envfile
        envs_exclude_unset_from_env: EnvVarsDict = dotenv_values(
            stream=StringIO(stdout_as_envfile)
        )
        assert envs_exclude_unset_from_env == mocked_envs

        stdout_as_json = cli_runner.invoke(
            cli,
            ["settings", "--show-secrets", "--exclude-unset", "--as-json"],
            catch_exceptions=False,
        ).stdout
        print(stdout_as_json)

        # parsing output as json file
        envs_exclude_unset_from_json = json.loads(stdout_as_json)
        assert envs_exclude_unset_from_json == {
            "APP_HOST": "localhost",
            "APP_PORT": 80,
            "APP_REQUIRED_PLUGIN": {
                "POSTGRES_HOST": "localhost",
                "POSTGRES_PORT": 5432,
                "POSTGRES_USER": "foo",
                "POSTGRES_PASSWORD": "secret",
                "POSTGRES_DB": "foodb",
                "POSTGRES_MAXSIZE": 20,
            },
        }
