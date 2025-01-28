# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_storage._meta import API_VERSION
from simcore_service_storage.cli import main
from simcore_service_storage.core.settings import ApplicationSettings
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK

    print(result.output)
    settings = ApplicationSettings(result.output)
    assert settings.model_dump() == ApplicationSettings.create_from_envs().model_dump()


def test_run(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout


# @pytest.mark.parametrize(
#     "arguments", ["--help", "run --help".split(), "settings --help".split()]
# )
# def test_cli_help(arguments: list[str] | str, cli_runner: CliRunner):
#     result = cli_runner.invoke(main, arguments)
#     assert result.exit_code == os.EX_OK, result


# def test_cli_settings_as_json(cli_runner: CliRunner):
#     result = cli_runner.invoke(main, ["settings", "--as-json"])
#     assert result.exit_code == os.EX_OK, result
#     # reuse resulting json to build settings
#     settings: dict = json.loads(result.stdout)
#     assert ApplicationSettings(settings)


# def test_cli_settings_env_file(cli_runner: CliRunner):
#     result = cli_runner.invoke(main, ["settings", "--compact"])
#     assert result.exit_code == os.EX_OK, result

#     # reuse resulting env_file to build settings
#     env_file = StringIO(result.stdout)

#     settings = dotenv_values(stream=env_file)
#     for key, value in settings.items():
#         with contextlib.suppress(json.decoder.JSONDecodeError):
#             settings[key] = json.loads(str(value))

#     assert ApplicationSettings(settings)
