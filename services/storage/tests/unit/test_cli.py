# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
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

    print(result.output)
    settings = ApplicationSettings(result.output)
    assert settings.model_dump() == ApplicationSettings.create_from_envs().model_dump()


def test_run(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout


def test_reconcile_zombies_help(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--help"])
    assert result.exit_code == os.EX_OK, result.output
    plain = _ANSI_ESCAPE_RE.sub("", result.output)
    assert "--s3-to-db" in plain
    assert "--db-to-s3" in plain
    assert "--multipart" in plain
    assert "--all" in plain
    assert "--dry-run" in plain


def test_reconcile_zombies_no_pass_selected(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["reconcile-zombies"])
    assert result.exit_code == 2
    assert "No pass selected" in result.output


# ---------------------------------------------------------------------------
# reconcile-zombies integration tests (mocked reconciliation module)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_app_lifecycle():
    """Patches create_app + LifespanManager so the CLI doesn't need real infra."""

    @asynccontextmanager
    async def _fake_lifespan(app):
        yield

    with (
        patch("simcore_service_storage.cli.create_app") as mock_create_app,
        patch("simcore_service_storage.cli.LifespanManager", side_effect=_fake_lifespan),
    ):
        mock_create_app.return_value = object()  # fake app
        yield


@pytest.fixture
def mock_recon():
    """Patches all reconciliation pass functions with controllable AsyncMocks."""
    with (
        patch("simcore_service_storage.cli.recon.reconcile_s3_to_db", new_callable=AsyncMock) as s3_to_db,
        patch("simcore_service_storage.cli.recon.reconcile_db_to_s3", new_callable=AsyncMock) as db_to_s3,
        patch(
            "simcore_service_storage.cli.recon.reconcile_abandoned_multipart_uploads", new_callable=AsyncMock
        ) as multipart,
    ):
        s3_to_db.return_value = 3
        db_to_s3.return_value = 7
        multipart.return_value = 2
        yield {"s3_to_db": s3_to_db, "db_to_s3": db_to_s3, "multipart": multipart}


def test_reconcile_zombies_all_flag_runs_all_passes(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--all"])

    assert result.exit_code == 0, result.output
    mock_recon["s3_to_db"].assert_called_once()
    mock_recon["db_to_s3"].assert_called_once()
    mock_recon["multipart"].assert_called_once()
    # Verify force=True is passed
    assert mock_recon["s3_to_db"].call_args.kwargs["force"] is True
    assert mock_recon["db_to_s3"].call_args.kwargs["force"] is True
    assert mock_recon["multipart"].call_args.kwargs["force"] is True
    # Verify output reports counts
    assert "3" in result.output
    assert "7" in result.output
    assert "2" in result.output
    assert "removed" in result.output


def test_reconcile_zombies_individual_s3_to_db_flag(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--s3-to-db"])

    assert result.exit_code == 0, result.output
    mock_recon["s3_to_db"].assert_called_once()
    mock_recon["db_to_s3"].assert_not_called()
    mock_recon["multipart"].assert_not_called()


def test_reconcile_zombies_individual_db_to_s3_flag(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--db-to-s3"])

    assert result.exit_code == 0, result.output
    mock_recon["db_to_s3"].assert_called_once()
    mock_recon["s3_to_db"].assert_not_called()
    mock_recon["multipart"].assert_not_called()


def test_reconcile_zombies_individual_multipart_flag(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--multipart"])

    assert result.exit_code == 0, result.output
    mock_recon["multipart"].assert_called_once()
    mock_recon["s3_to_db"].assert_not_called()
    mock_recon["db_to_s3"].assert_not_called()


def test_reconcile_zombies_combined_flags(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--s3-to-db", "--multipart"])

    assert result.exit_code == 0, result.output
    mock_recon["s3_to_db"].assert_called_once()
    mock_recon["multipart"].assert_called_once()
    mock_recon["db_to_s3"].assert_not_called()


def test_reconcile_zombies_dry_run_flag_passes_dry_run_true(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--all", "--dry-run"])

    assert result.exit_code == 0, result.output
    # All passes called with dry_run=True
    assert mock_recon["s3_to_db"].call_args.kwargs["dry_run"] is True
    assert mock_recon["db_to_s3"].call_args.kwargs["dry_run"] is True
    assert mock_recon["multipart"].call_args.kwargs["dry_run"] is True
    # Output uses dry-run wording
    assert "[DRY-RUN]" in result.output
    assert "found" in result.output


def test_reconcile_zombies_dry_run_output_says_found_not_removed(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--all", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "found" in result.output
    # "removed" and "aborted" should NOT appear in the summary lines
    lines = result.output.strip().split("\n")
    summary_lines = [
        line
        for line in lines
        if line.strip().startswith("S3") or line.strip().startswith("DB") or line.strip().startswith("Abandoned")
    ]
    for line in summary_lines:
        assert "removed" not in line
        assert "aborted" not in line


def test_reconcile_zombies_normal_mode_output_says_removed(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    result = cli_runner.invoke(main, ["reconcile-zombies", "--all"])

    assert result.exit_code == 0, result.output
    lines = result.output.strip().split("\n")
    summary_lines = [
        line
        for line in lines
        if line.strip().startswith("S3") or line.strip().startswith("DB") or line.strip().startswith("Abandoned")
    ]
    assert any("removed" in line for line in summary_lines)
    assert any("aborted" in line for line in summary_lines)


def test_reconcile_zombies_zero_counts_reported(
    cli_runner: CliRunner, app_environment: EnvVarsDict, mock_app_lifecycle, mock_recon
):
    mock_recon["s3_to_db"].return_value = 0
    mock_recon["db_to_s3"].return_value = 0
    mock_recon["multipart"].return_value = 0

    result = cli_runner.invoke(main, ["reconcile-zombies", "--all"])

    assert result.exit_code == 0, result.output
    assert "Reconciliation complete" in result.output
    # All zeros reported
    lines = result.output.strip().split("\n")
    count_lines = [line for line in lines if ":" in line and any(c.isdigit() for c in line)]
    for line in count_lines:
        assert "0" in line
