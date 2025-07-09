import os
import shutil
import traceback
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import Result
from service_integration import __version__


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


def test_cli_help(run_program_with_args: Callable):
    result = run_program_with_args(
        "--help",
    )
    assert result.exit_code == os.EX_OK, _format_cli_error(result)


def test_cli_version(run_program_with_args: Callable):
    result = run_program_with_args(
        "--version",
    )
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert __version__ == result.output.strip()


@pytest.fixture
def copy_tests_data_dir(tests_data_dir: Path, tmp_path: Path) -> Path:
    new_dir_path = tmp_path / "copy_tests_data_dir"
    new_dir_path.mkdir(exist_ok=True, parents=True)

    for item in tests_data_dir.glob("*"):
        print(f"Copying {item} to {new_dir_path / item.name}")
        shutil.copy2(item, new_dir_path / item.name)

    return new_dir_path


def test_cli_legacy_escape(copy_tests_data_dir: Path, run_program_with_args: Callable):
    result = run_program_with_args(
        "legacy-escape", "--osparc-config-dirname", copy_tests_data_dir
    )
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    # NOTE only 1 file will have a sequnce that will be escaped
    assert (
        result.output.strip()
        == f"Escaped sequnce in {copy_tests_data_dir}/docker-compose-meta.yml"
    )
