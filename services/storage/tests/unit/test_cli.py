# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_storage._meta import API_VERSION
from simcore_service_storage.cli import main
from simcore_service_storage.core.settings import ApplicationSettings
from typer.testing import CliRunner

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def test_cli_help_and_version(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK

    settings = ApplicationSettings(result.output)
    assert settings.model_dump() == ApplicationSettings.create_from_envs().model_dump()


def test_run(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout


def test_reconcile_help(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["reconcile", "--help"])
    assert result.exit_code == os.EX_OK, result.output
    plain = _ANSI_ESCAPE_RE.sub("", result.output)
    assert "--dry-run" in plain


@asynccontextmanager
async def _fake_lifespan(_app):
    yield


def test_reconcile_runs_full_pass(cli_runner: CliRunner, app_environment: EnvVarsDict):
    with (
        patch("simcore_service_storage.cli.create_app") as mock_create_app,
        patch("simcore_service_storage.cli.LifespanManager", side_effect=_fake_lifespan),
        patch("simcore_service_storage.cli.recon.run_reconciliation_pass", new_callable=AsyncMock) as mock_run,
    ):
        mock_create_app.return_value = object()
        mock_run.return_value.unreachable_removed = 3
        mock_run.return_value.dangling_removed = 7
        mock_run.return_value.orphan_prefixes_removed = 2
        mock_run.return_value.total_removed = 12

        result = cli_runner.invoke(main, ["reconcile", "--execute"])

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["force"] is True
    assert mock_run.call_args.kwargs["dry_run"] is False
    assert "Reconciliation complete" in result.output
    assert "12" in result.output


def test_reconcile_dry_run(cli_runner: CliRunner, app_environment: EnvVarsDict):
    with (
        patch("simcore_service_storage.cli.create_app") as mock_create_app,
        patch("simcore_service_storage.cli.LifespanManager", side_effect=_fake_lifespan),
        patch("simcore_service_storage.cli.recon.run_reconciliation_pass", new_callable=AsyncMock) as mock_run,
    ):
        mock_create_app.return_value = object()
        mock_run.return_value.unreachable_removed = 1
        mock_run.return_value.dangling_removed = 1
        mock_run.return_value.orphan_prefixes_removed = 1
        mock_run.return_value.total_removed = 3

        result = cli_runner.invoke(main, ["reconcile", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["dry_run"] is True
    assert "[DRY-RUN]" in result.output
    assert "found" in result.output
