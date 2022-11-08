# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from simcore_service_webserver.cli import main
from typer.testing import CliRunner


def test_main_cli(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert "settings" in result.stdout
    assert "run" in result.stdout
    assert result.exit_code == 0

    result = cli_runner.invoke(main, ["settings", "--help"])
    assert result.exit_code == 0

    result = cli_runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
