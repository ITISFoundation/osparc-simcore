# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
import os
from io import StringIO
from typing import Any, Callable, ContextManager, Dict, Type

import pytest
import typer
from dotenv import dotenv_values
from pydantic import ValidationError
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_as_envfile
from settings_library.base import BaseCustomSettings
from settings_library.utils_cli import create_settings_command, print_as_envfile
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


# TESTS -----------------------------------------------------------------------------------


def test_compose_commands(cli: typer.Typer, cli_runner: CliRunner):
    result = cli_runner.invoke(cli, ["--help"])
    print(result.stdout)
    assert result.exit_code == 0, result

    # first command
    result = cli_runner.invoke(cli, ["run", "--help"])
    print(result.stdout)
    assert result.exit_code == 0, result

    # settings command
    result = cli_runner.invoke(cli, ["settings", "--help"])
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
    --help                          Show this message and exit.
"""


def test_settings_as_json(
    cli: typer.Typer, fake_settings_class, mock_environment, cli_runner: CliRunner
):

    result = cli_runner.invoke(cli, ["settings", "--as-json"])
    print(result.stdout)

    # reuse resulting json to build settings
    settings: Dict = json.loads(result.stdout)
    assert fake_settings_class.parse_obj(settings)


def test_settings_as_env_file(
    cli: typer.Typer, fake_settings_class, mock_environment, cli_runner: CliRunner
):
    # ANE -> PC: this test will be left in place but the feature will
    # not be considered for parsing settings via Pudantic as there
    # is no out of the box support

    result = cli_runner.invoke(cli, ["settings", "--compact"])
    print(result.stdout)

    # reuse resulting env_file to build settings
    env_file = StringIO(result.stdout)

    settings: Dict = dotenv_values(stream=env_file)
    for key, value in settings.items():
        try:
            settings[key] = json.loads(str(value))
        except json.decoder.JSONDecodeError:
            pass

    assert fake_settings_class.parse_obj(settings)


def test_supported_parsable_env_formats(
    cli: typer.Typer,
    fake_settings_class: Type[BaseCustomSettings],
    cli_runner: CliRunner,
    mocked_settings_cls_env: str,
    mocked_environment: Callable[[str], ContextManager[None]],
) -> None:
    with mocked_environment(mocked_settings_cls_env):
        settings_object = fake_settings_class()
        assert settings_object

        setting_env_content = cli_runner.invoke(
            cli,
            ["settings"],
        ).stdout
        print(setting_env_content)

    # parse standard format
    with mocked_environment(setting_env_content):
        settings_object = fake_settings_class()
        assert settings_object


@pytest.mark.skip(reason="WIP")
def test_unsupported_env_format(
    cli: typer.Typer,
    fake_settings_class: Type[BaseCustomSettings],
    cli_runner: CliRunner,
    mocked_settings_cls_env: str,
    mocked_environment: Callable[[str], ContextManager[None]],
) -> None:
    with mocked_environment(mocked_settings_cls_env):
        settings_object = fake_settings_class()
        assert settings_object

        setting_env_content_compact = cli_runner.invoke(
            cli,
            ["settings", "--compact"],
        ).stdout
        print(setting_env_content_compact)

    # The compact format is not parsable directly by Pydantic.
    # Also removed compact and mixed compact mocks .env files
    with pytest.raises(ValidationError):
        # if support for this test is ever added (meaning this test will fail)
        # please redefine the below files inside the mocks directory
        # ".env-compact", ".env-granular", ".env-fails", ".env-mixed", ".env-sample"
        # removed by https://github.com/ITISFoundation/osparc-simcore/pull/2438

        # parse compact format
        with mocked_environment(setting_env_content_compact):
            print(json.dumps(dict(os.environ), indent=1))
            settings_object = fake_settings_class()
            assert settings_object


def test_compact_format(monkeypatch, fake_settings_class):
    compact_envs: EnvVarsDict = setenvs_as_envfile(
        monkeypatch,
        """
    APP_HOST=localhost
    APP_PORT=80
    APP_OPTIONAL_ADDON='{"MODULE_VALUE": 10, "MODULE_VALUE_DEFAULT": 42}'
    APP_REQUIRED_PLUGIN='{"POSTGRES_HOST": "localhost", "POSTGRES_PORT": 5432, "POSTGRES_USER": "foo", "POSTGRES_PASSWORD": "**********", "POSTGRES_DB": "foodb", "POSTGRES_MINSIZE": 1, "POSTGRES_MAXSIZE": 50, "POSTGRES_CLIENT_NAME": "None"}'
    """,
    )

    settings_from_envs1 = fake_settings_class()
    settings_from_init = fake_settings_class(**envs_to_kwargs(compact_envs))

    assert settings_from_envs1 == settings_from_init

    print_as_envfile(settings_from_envs1, compact=False, verbose=True)


def test_granular_format(monkeypatch, fake_settings_class):
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
    POSTGRES_PASSWORD=**********
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
            "POSTGRES_PASSWORD": "**********",
            "POSTGRES_DB": "foodb",
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_CLIENT_NAME": None,
        },
    )
