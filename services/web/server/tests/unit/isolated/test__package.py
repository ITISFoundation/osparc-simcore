# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pytest_simcore.helpers.utils_pylint import (
    assert_no_pdb_in_code,
    assert_pylint_is_passing,
)
from simcore_service_webserver.cli import main
from typer.testing import CliRunner


def test_run_pylint(pylintrc, package_dir):
    # fixtures in pytest_simcore.environs
    assert_pylint_is_passing(pylintrc=pylintrc, package_dir=package_dir)


def test_no_pdbs_in_place(package_dir):
    # fixtures in pytest_simcore.environs
    assert_no_pdb_in_code(code_dir=package_dir)


def test_main_cli(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert "settings" in result.stdout
    assert "run" in result.stdout
    assert result.exit_code == 0

    result = cli_runner.invoke(main, ["settings", "--help"])
    assert result.exit_code == 0

    result = cli_runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
