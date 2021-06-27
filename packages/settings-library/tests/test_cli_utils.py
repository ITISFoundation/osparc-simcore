# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
from io import StringIO
from textwrap import dedent
from typing import Dict, Type

import pytest
import typer
from dotenv import dotenv_values
from settings_library.base import BaseCustomSettings
from settings_library.cli_utils import create_settings_command
from typer.testing import CliRunner

log = logging.getLogger(__name__)

runner = CliRunner()


@pytest.fixture
def cli(settings_cls: Type[BaseCustomSettings]):
    main = typer.Typer(name="app")

    @main.command()
    def run():
        """Emulates run"""
        typer.secho("Starting app ... ")
        typer.secho("Resolving settings ...", nl=False)
        typer.secho("DONE", fg=typer.colors.GREEN)

    # adds settings command
    settings_cmd = create_settings_command(settings_cls, log)
    main.command()(settings_cmd)

    return main


def test_compose_commands(cli):
    result = runner.invoke(cli, ["--help"])
    print(result.stdout)
    assert result.exit_code == 0

    # first command
    result = runner.invoke(cli, ["run", "--help"])
    print(result.stdout)
    assert result.exit_code == 0

    # settings command
    result = runner.invoke(cli, ["settings", "--help"])
    print(result.stdout)

    assert "--compact" in result.stdout
    assert result.exit_code == 0

    def extract_lines(text):
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines

    assert extract_lines(HELP) == extract_lines(result.stdout)


HELP = """
    Usage: app settings [OPTIONS]

    Resolves settings and prints envfile

    Options:
    --as-json / --no-as-json        [default: False]
    --as-json-schema / --no-as-json-schema
                                    [default: False]
    --compact / --no-compact        Print compact form  [default: False]
    --verbose / --no-verbose        [default: False]
    --help                          Show this message and exit.
"""


def test_settings_as_json(cli, settings_cls, mock_environment):

    result = runner.invoke(cli, ["settings", "--as-json"])
    print(result.stdout)

    # reuse resulting json to build settings
    settings: Dict = json.loads(result.stdout)
    assert settings_cls.parse_obj(settings)


def test_settings_as_env_file(cli, settings_cls, mock_environment):
    result = runner.invoke(cli, ["settings", "--compact"])
    print(result.stdout)

    # reuse resulting env_file to build settings
    env_file = StringIO(result.stdout)

    settings: Dict = dotenv_values(stream=env_file)
    for key, value in settings.items():
        try:
            settings[key] = json.loads(str(value))
        except json.decoder.JSONDecodeError:
            pass

    assert settings_cls.parse_obj(settings)
