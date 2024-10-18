# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
from collections.abc import Callable
from io import StringIO
from typing import Any

import pytest
import typer
from dotenv import dotenv_values
from pydantic import Field, SecretStr
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_envfile
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.base import BaseCustomSettings
from settings_library.utils_cli import (
    create_settings_command,
    create_version_callback,
    model_dump_with_secrets,
    print_as_envfile,
    print_as_json,
)
from typer.testing import CliRunner

log = logging.getLogger(__name__)


def envs_to_kwargs(envs: EnvVarsDict) -> dict[str, Any]:
    kwargs = {}
    for k, v in envs.items():
        if v is not None:
            try:
                kwargs[k] = json.loads(v)
            except json.JSONDecodeError:
                kwargs[k] = v
    return kwargs


@pytest.fixture
def fake_version() -> str:
    return "0.0.1-alpha"


@pytest.fixture
def cli(
    fake_settings_class: type[BaseCustomSettings], fake_version: str
) -> typer.Typer:
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
    main.callback()(create_version_callback(fake_version))

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


@pytest.fixture
def export_as_dict() -> Callable:
    def _export(model_obj, **export_options):
        return model_dump_with_secrets(model_obj, show_secrets=True, **export_options)

    return _export


def test_compose_commands(cli: typer.Typer, cli_runner: CliRunner):
    # NOTE: this tests is mostly here to raise awareness about what options
    # are exposed in the CLI so we can add tests if there is any update
    #
    result = cli_runner.invoke(cli, ["--help"], catch_exceptions=False)
    print(result.stdout)
    assert result.exit_code == 0, result

    result = cli_runner.invoke(cli, ["--version"], catch_exceptions=False)
    print(result.stdout)
    assert result.exit_code == 0, result

    # first command
    result = cli_runner.invoke(cli, ["run", "--help"], catch_exceptions=False)
    print(result.stdout)
    assert result.exit_code == 0, result

    # settings command
    result = cli_runner.invoke(cli, ["settings", "--help"], catch_exceptions=False)
    print(result.stdout)
    assert result.exit_code == 0, result

    received_help = result.stdout

    assert "compact" in result.stdout, f"got instead {received_help=}"
    assert "as-json" in received_help, f"got instead {received_help=}"
    assert "help" in received_help, f"got instead {received_help=}"


def test_settings_as_json(
    cli: typer.Typer,
    fake_settings_class: type[BaseCustomSettings],
    mock_environment,
    cli_runner: CliRunner,
):
    result = cli_runner.invoke(
        cli, ["settings", "--as-json", "--show-secrets"], catch_exceptions=False
    )
    print(result.stdout)

    # reuse resulting json to build settings
    settings: dict = json.loads(result.stdout)
    assert fake_settings_class.model_validate(settings)


def test_settings_as_json_schema(
    cli: typer.Typer,
    fake_settings_class: type[BaseCustomSettings],
    mock_environment,
    cli_runner: CliRunner,
):
    result = cli_runner.invoke(
        cli, ["settings", "--as-json-schema"], catch_exceptions=False
    )
    print(result.stdout)

    # reuse resulting json to build settings
    json.loads(result.stdout)


def test_cli_default_settings_envs(
    cli: typer.Typer,
    fake_settings_class: type[BaseCustomSettings],
    fake_granular_env_file_content: str,
    export_as_dict: Callable,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    with monkeypatch.context() as patch:
        setenvs_from_envfile(patch, fake_granular_env_file_content)

        cli_settings_output = cli_runner.invoke(
            cli,
            ["settings", "--show-secrets"],
            catch_exceptions=False,
        ).stdout

    print(cli_settings_output)

    # now let's use these as env vars
    with monkeypatch.context() as patch:
        setenvs_from_envfile(
            patch,
            cli_settings_output,
        )
        settings_object = fake_settings_class()
        assert settings_object

        settings_dict_wo_secrets = export_as_dict(settings_object)
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
    fake_settings_class: type[BaseCustomSettings],
    fake_granular_env_file_content: str,
    export_as_dict: Callable,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    with monkeypatch.context() as patch:
        setenvs_from_envfile(patch, fake_granular_env_file_content)

        settings_1 = fake_settings_class()

        settings_1_dict_wo_secrets = export_as_dict(settings_1)
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
            ["settings", "--compact", "--show-secrets"],
            catch_exceptions=False,
        ).stdout

    # now we use these as env vars
    print(setting_env_content_compact)

    with monkeypatch.context() as patch:
        mocked_envs_2: EnvVarsDict = setenvs_from_envfile(
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
    fake_settings_class: type[BaseCustomSettings],
):
    compact_envs: EnvVarsDict = setenvs_from_envfile(
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
    fake_settings_class: type[BaseCustomSettings],
):
    setenvs_from_envfile(
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
    # minimal envfile
    mocked_envs: EnvVarsDict = setenvs_from_envfile(
        monkeypatch,
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


@pytest.mark.xfail(
    reason="--show-secrets and --exclude-unset still not implemented with --as-json"
)
def test_cli_settings_exclude_unset_as_json(
    cli: typer.Typer,
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
):
    # minimal envfile
    setenvs_from_envfile(
        monkeypatch,
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


def test_print_as(capsys: pytest.CaptureFixture):
    class FakeSettings(BaseCustomSettings):
        INTEGER: int = Field(..., description="Some info")
        SECRET: SecretStr

    settings_obj = FakeSettings(INTEGER=1, SECRET="secret")  # type: ignore

    print_as_envfile(settings_obj, compact=True, verbose=True, show_secrets=True)
    captured = capsys.readouterr()
    assert "secret" in captured.out
    assert "Some info" in captured.out

    print_as_envfile(settings_obj, compact=True, verbose=False, show_secrets=True)
    captured = capsys.readouterr()
    assert "secret" in captured.out
    assert "Some info" not in captured.out

    print_as_envfile(settings_obj, compact=True, verbose=False, show_secrets=False)
    captured = capsys.readouterr()
    assert "secret" not in captured.out
    assert "Some info" not in captured.out

    print_as_json(
        settings_obj, compact=True, show_secrets=False, json_serializer=json.dumps
    )
    captured = capsys.readouterr()
    assert "secret" not in captured.out
    assert "**" in captured.out
    assert "Some info" not in captured.out
