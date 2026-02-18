# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_catalog._meta import API_VERSION
from simcore_service_catalog.cli import main
from simcore_service_catalog.core.settings import ApplicationSettings
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


def test_registry_check_passes_with_valid_services(
    cli_runner: CliRunner,
    monkeypatch,
    expected_director_rest_api_list_services: list[dict],
):
    async def _mock_fetch_registry_services(*, base_url: str, timeout_s: float):
        return [expected_director_rest_api_list_services[0]]

    monkeypatch.setattr(
        "simcore_service_catalog.cli._fetch_registry_services",
        _mock_fetch_registry_services,
    )

    result = cli_runner.invoke(main, ["registry-check"])

    assert result.exit_code == os.EX_OK, result.output
    assert "No invalid services detected" in result.output


def test_registry_check_fails_with_invalid_services(
    cli_runner: CliRunner,
    monkeypatch,
):
    async def _mock_fetch_registry_services(*, base_url: str, timeout_s: float):
        return [{"key": "simcore/services/dynamic/invalid", "version": "not-semver"}]

    monkeypatch.setattr(
        "simcore_service_catalog.cli._fetch_registry_services",
        _mock_fetch_registry_services,
    )

    result = cli_runner.invoke(main, ["registry-check"])

    assert result.exit_code == 1, result.output
    assert "Detected 1 invalid services" in result.output


def test_registry_delete_asks_confirmation_and_calls_delete(cli_runner: CliRunner, monkeypatch):
    calls: list[tuple[str, str, str, float]] = []

    async def _mock_delete_registry_service(*, base_url: str, service_key: str, service_version: str, timeout_s: float):
        calls.append((base_url, service_key, service_version, timeout_s))

    monkeypatch.setattr(
        "simcore_service_catalog.cli._delete_registry_service",
        _mock_delete_registry_service,
    )

    result = cli_runner.invoke(
        main,
        ["registry-delete", "simcore/services/dynamic/sleeper", "1.2.3"],
        input="y\n",
    )

    assert result.exit_code == os.EX_OK, result.output
    assert len(calls) == 1


def test_registry_delete_can_skip_confirmation_with_yes(cli_runner: CliRunner, monkeypatch):
    calls: list[tuple[str, str, str, float]] = []

    async def _mock_delete_registry_service(*, base_url: str, service_key: str, service_version: str, timeout_s: float):
        calls.append((base_url, service_key, service_version, timeout_s))

    monkeypatch.setattr(
        "simcore_service_catalog.cli._delete_registry_service",
        _mock_delete_registry_service,
    )

    result = cli_runner.invoke(
        main,
        ["registry-delete", "simcore/services/dynamic/sleeper", "1.2.3", "--yes"],
    )

    assert result.exit_code == os.EX_OK, result.output
    assert len(calls) == 1
