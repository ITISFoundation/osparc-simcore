# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import contextlib
import json
import os
from io import StringIO

import pytest
from dotenv import dotenv_values
from simcore_service_storage.cli import main
from simcore_service_storage.settings import Settings


@pytest.mark.parametrize(
    "arguments", ["--help", "run --help".split(), "settings --help".split()]
)
def test_cli_help(arguments, cli_runner):
    result = cli_runner.invoke(main, arguments)
    print(result.stdout)
    assert result.exit_code == os.EX_OK, result
    assert "Usage: simcore-service-storage" in result.stdout


def test_cli_settings_as_json(project_env_devel_environment, cli_runner):
    # $ (set -o allexport; source .env; simcore-service-storage settings  --as-json ) > env.json

    result = cli_runner.invoke(main, ["settings", "--as-json"])
    print(result.stdout)

    # reuse resulting json to build settings
    settings: dict = json.loads(result.stdout)
    assert Settings.parse_obj(settings)


def test_cli_settings_env_file(project_env_devel_environment, cli_runner):
    # $ (set -o allexport; source .env; simcore-service-storage settings  --compact ) > .env
    result = cli_runner.invoke(main, ["settings", "--compact"])
    print(result.stdout)

    # reuse resulting env_file to build settings
    env_file = StringIO(result.stdout)

    settings: dict = dotenv_values(stream=env_file)
    for key, value in settings.items():
        with contextlib.suppress(json.decoder.JSONDecodeError):
            settings[key] = json.loads(str(value))

    assert Settings.parse_obj(settings)
