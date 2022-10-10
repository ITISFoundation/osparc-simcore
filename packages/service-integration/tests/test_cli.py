from typing import Callable

from service_integration import __version__


def test_cli_help(run_program_with_args: Callable):
    result = run_program_with_args(
        "--help",
    )
    assert result.exit_code == 0


def test_cli_version(run_program_with_args: Callable):
    result = run_program_with_args(
        "--version",
    )
    assert result.exit_code == 0
    assert __version__ == result.output.strip()
