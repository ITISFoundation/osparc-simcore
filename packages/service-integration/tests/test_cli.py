from typing import Callable


def test_cli_app(run_program_with_args: Callable):
    result = run_program_with_args(
        "--help",
    )
    assert result.exit_code == 0
    assert "--version" in result.output
    assert "bump-version " in result.output
