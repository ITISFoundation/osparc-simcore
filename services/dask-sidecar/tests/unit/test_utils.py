# pylint: disable=no-value-for-parameter
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import asyncio
from typing import Dict, List, Optional
from unittest import mock

import aiodocker
import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from simcore_service_dask_sidecar.utils import cluster_id, num_available_gpus


@pytest.fixture
def mock_service_envs(
    mock_env_devel_environment: Dict[str, Optional[str]], monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME", "simcore_computational_shared_data"
    )
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_FOLDER", "/home/scu/computational_shared_data"
    )


@pytest.fixture(scope="function")
def mock_aiodocker(mocker: MockerFixture) -> mock.MagicMock:
    mock_docker = mocker.patch(
        "simcore_service_dask_sidecar.utils.aiodocker.Docker", autospec=True
    )
    return mock_docker


@pytest.mark.parametrize(
    "docker_engine_labels, expected_id",
    [
        ({}, "CLUSTER_0"),
        ({"invalidlabel"}, "CLUSTER_0"),
        (["blahblah", "cluster_id=MyAwesomeClusterID"], "CLUSTER_MyAwesomeClusterID"),
    ],
)
def test_cluster_id(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    docker_engine_labels: List[str],
    expected_id: str,
    mock_aiodocker: mock.MagicMock,
):

    mock_aiodocker.return_value.__aenter__.return_value.system.info.return_value = {
        "Labels": docker_engine_labels
    }
    the_cluster_id = cluster_id()
    assert the_cluster_id == expected_id


def test_num_available_gpus_returns_0_when_container_not_created(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value = (
        None
    )

    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_container_throws_exception_on_run(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.side_effect = (
        aiodocker.exceptions.DockerError(
            status="testing bad status", data={"message": "error when running"}
        )
    )
    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_no_status_code_returned(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.return_value = {
        "mistakeinthereturnvalue": "kdsfjh"
    }
    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_bad_status_code_returned(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.return_value = {
        "StatusCode": 1
    }
    assert num_available_gpus() == 0


def test_num_available_gpus_returns_0_when_container_wait_timesout(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    mock_aiodocker: mock.MagicMock,
):
    mock_aiodocker.return_value.__aenter__.return_value.containers.run.return_value.wait.side_effect = (
        asyncio.TimeoutError()
    )
    assert num_available_gpus() == 0


@pytest.mark.parametrize(
    "container_logs, expected_num_gpus",
    [([], 0), (["gpu1"], 1), (["gpu1", "gpu2", "gpu4"], 3)],
)
def test_num_available_gpus(
    loop: asyncio.events.AbstractEventLoop,
    mock_service_envs: None,
    container_logs: List[str],
    expected_num_gpus: int,
    mock_aiodocker: mock.MagicMock,
):
    # default with mock should return 0 gpus
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
