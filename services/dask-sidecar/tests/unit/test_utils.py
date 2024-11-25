# pylint: disable=no-value-for-parameter
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import asyncio
from unittest import mock

import aiodocker
import pytest
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dask_sidecar.utils import num_available_gpus


@pytest.fixture
def mock_aiodocker(mocker: MockerFixture) -> mock.MagicMock:
    return mocker.patch(
        "simcore_service_dask_sidecar.utils.aiodocker.Docker", autospec=True
    )


def test_num_available_gpus_returns_0_when_container_not_created(
    event_loop: asyncio.events.AbstractEventLoop,
    app_environment: EnvVarsDict,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value = (
        None
    )

    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_container_throws_exception_on_run(
    event_loop: asyncio.events.AbstractEventLoop,
    app_environment: EnvVarsDict,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.side_effect = (
        aiodocker.exceptions.DockerError(
            status="testing bad status", data={"message": "error when running"}
        )
    )
    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_no_status_code_returned(
    event_loop: asyncio.events.AbstractEventLoop,
    app_environment: EnvVarsDict,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.return_value = {
        "mistakeinthereturnvalue": "kdsfjh"
    }
    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_bad_status_code_returned(
    event_loop: asyncio.events.AbstractEventLoop,
    app_environment: EnvVarsDict,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.return_value = {
        "StatusCode": 1
    }
    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_container_wait_timesout(
    event_loop: asyncio.events.AbstractEventLoop,
    app_environment: EnvVarsDict,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.side_effect = (
        TimeoutError()
    )
    assert num_available_gpus() == 0


@pytest.mark.parametrize(
    "container_logs, expected_num_gpus",
    [([], 0), (["gpu1"], 1), (["gpu1", "gpu2", "gpu4"], 3)],
)
def test_num_available_gpus(
    event_loop: asyncio.events.AbstractEventLoop,
    app_environment: EnvVarsDict,
    container_logs: list[str],
    expected_num_gpus: int,
    mock_aiodocker: mock.MagicMock,
):
    # default with mock should return 0 gpus
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.return_value = {
        "StatusCode": 0
    }
    assert num_available_gpus() == 0

    # add the correct log
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.log.return_value = (
        container_logs
    )
    # set the correct status code
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.return_value = {
        "StatusCode": 0
    }
    assert num_available_gpus() == expected_num_gpus
