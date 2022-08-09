# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_sidecar.cli import main
from typer.testing import CliRunner

# FIXTURES


@pytest.fixture
def cli_runner(mock_environment: EnvVarsDict) -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_rabbitmq(mocker: MockerFixture) -> None:
    mocker.patch("simcore_service_dynamic_sidecar.cli.RabbitMQ", spec=True)


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


# TESTS


def test_outputs_push_interface(
    cli_runner: CliRunner, mock_rabbitmq: None, mock_data_manager: None
):
    result = cli_runner.invoke(main, ["state-save"])
    assert result.exit_code == 0
    assert result.stdout == "state save finished successfully\n"


def test_state_save_interface(
    cli_runner: CliRunner, mock_rabbitmq: None, mock_nodeports: None
):
    result = cli_runner.invoke(main, ["outputs-push"])
    assert result.exit_code == 0
    assert result.stdout == "output ports push finished successfully\n"
