# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import os
import traceback

import pytest
from click.testing import Result
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_sidecar.cli import main
from typer.testing import CliRunner


@pytest.fixture
def cli_runner(mock_environment: EnvVarsDict) -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_data_manager(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks.data_manager",
        spec=True,
    )


@pytest.fixture
def mock_nodeports(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks.nodeports",
        spec=True,
    )


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


def test_list_state_dirs(cli_runner: CliRunner, mock_data_manager: None):
    result = cli_runner.invoke(main, ["state-list-dirs"])
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert result.stdout.strip() == "\n".join(
        [f"Entries in /data/state_dir{i}: []" for i in range(4)]
    )


def test_outputs_push_interface(cli_runner: CliRunner, mock_data_manager: None):
    result = cli_runner.invoke(main, ["state-save"])
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert result.stdout == "state save finished successfully\n"
    print(result)


def test_state_save_interface(cli_runner: CliRunner, mock_nodeports: None):
    result = cli_runner.invoke(main, ["outputs-push"])
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert result.stdout == "output ports push finished successfully\n"
    print(result)
