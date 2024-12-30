# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_mock
from aiodocker.docker import Docker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceRunID
from servicelib.rabbitmq.rpc_interfaces.agent.errors import (
    NoServiceVolumesFoundRPCError,
)
from simcore_service_agent.services.volumes_manager import VolumesManager
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)
from utils import VOLUMES_TO_CREATE, get_source


@dataclass
class MockedVolumesProxy:
    service_run_id: ServiceRunID
    volumes: set[str] = field(default_factory=set)

    def add_unused_volumes_for_service(self, node_id: NodeID) -> None:
        for folder_name in VOLUMES_TO_CREATE:
            volume_name = get_source(
                self.service_run_id, node_id, Path("/apath") / folder_name
            )
            self.volumes.add(volume_name)

    def remove_volume(self, volume_name: str) -> None:
        self.volumes.remove(volume_name)

    def get_unused_dynamc_sidecar_volumes(self) -> set[str]:
        return deepcopy(self.volumes)


@pytest.fixture
async def mock_docker_utils(
    mocker: pytest_mock.MockerFixture, service_run_id: ServiceRunID
) -> MockedVolumesProxy:
    proxy = MockedVolumesProxy(service_run_id)

    async def _remove_volume(
        app: FastAPI, docker: Docker, *, volume_name: str, requires_backup: bool
    ) -> None:
        proxy.remove_volume(volume_name)

    async def _get_unused_dynamc_sidecar_volumes(app: FastAPI) -> set[str]:
        return proxy.get_unused_dynamc_sidecar_volumes()

    mocker.patch(
        "simcore_service_agent.services.volumes_manager.remove_volume",
        side_effect=_remove_volume,
    )

    mocker.patch(
        "simcore_service_agent.services.volumes_manager.get_unused_dynamc_sidecar_volumes",
        side_effect=_get_unused_dynamc_sidecar_volumes,
    )

    return proxy


@pytest.fixture
def spy_remove_volume(
    mocker: pytest_mock.MockerFixture, mock_docker_utils: MockedVolumesProxy
) -> AsyncMock:
    return mocker.spy(mock_docker_utils, "remove_volume")


@pytest.fixture
async def volumes_manager() -> VolumesManager:
    # NOTE: background tasks are disabled on purpose
    return VolumesManager(
        app=FastAPI(),
        book_keeping_interval=timedelta(seconds=1),
        volume_cleanup_interval=timedelta(seconds=1),
        remove_volumes_inactive_for=timedelta(seconds=0.1).total_seconds(),
    )


@pytest.mark.parametrize("service_count", [1, 3])
async def test_volumes_manager_remove_all_volumes(
    service_count: int,
    mock_docker_utils: MockedVolumesProxy,
    spy_remove_volume: AsyncMock,
    volumes_manager: VolumesManager,
):
    assert spy_remove_volume.call_count == 0

    for _ in range(service_count):
        mock_docker_utils.add_unused_volumes_for_service(uuid4())
    assert spy_remove_volume.call_count == 0
    assert (
        len(mock_docker_utils.get_unused_dynamc_sidecar_volumes())
        == len(VOLUMES_TO_CREATE) * service_count
    )

    await volumes_manager.remove_all_volumes()
    assert spy_remove_volume.call_count == len(VOLUMES_TO_CREATE) * service_count
    assert len(mock_docker_utils.get_unused_dynamc_sidecar_volumes()) == 0


async def test_volumes_manager_remove_service_volumes(
    mock_docker_utils: MockedVolumesProxy,
    spy_remove_volume: AsyncMock,
    volumes_manager: VolumesManager,
):
    assert spy_remove_volume.call_count == 0
    mock_docker_utils.add_unused_volumes_for_service(uuid4())
    node_id_to_remvoe = uuid4()
    mock_docker_utils.add_unused_volumes_for_service(node_id_to_remvoe)

    assert spy_remove_volume.call_count == 0
    assert (
        len(mock_docker_utils.get_unused_dynamc_sidecar_volumes())
        == len(VOLUMES_TO_CREATE) * 2
    )

    await volumes_manager.remove_service_volumes(node_id_to_remvoe)

    assert spy_remove_volume.call_count == len(VOLUMES_TO_CREATE)
    unused_volumes = mock_docker_utils.get_unused_dynamc_sidecar_volumes()
    assert len(unused_volumes) == len(VOLUMES_TO_CREATE)
    for volume_name in unused_volumes:
        assert f"{node_id_to_remvoe}" not in volume_name


@pytest.fixture
async def mock_wait_for_unused_service_volumes(
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch(
        "simcore_service_agent.services.volumes_manager._WAIT_FOR_UNUSED_SERVICE_VOLUMES",
        timedelta(seconds=2),
    )


async def test_volumes_manager_remove_service_volumes_when_volume_does_not_exist(
    mock_wait_for_unused_service_volumes: None,
    volumes_manager: VolumesManager,
):
    not_existing_service = uuid4()
    with pytest.raises(NoServiceVolumesFoundRPCError):
        await volumes_manager.remove_service_volumes(not_existing_service)


async def test_volumes_manager_periodic_task_cleanup(
    mock_docker_utils: MockedVolumesProxy,
    spy_remove_volume: AsyncMock,
    volumes_manager: VolumesManager,
):
    async def _run_volumes_clennup() -> None:
        await volumes_manager._bookkeeping_task()  # noqa: SLF001
        await volumes_manager._periodic_volmue_cleanup_task()  # noqa: SLF001

    await _run_volumes_clennup()
    assert spy_remove_volume.call_count == 0

    mock_docker_utils.add_unused_volumes_for_service(uuid4())
    await _run_volumes_clennup()
    assert spy_remove_volume.call_count == 0

    # wait for the amount of time to pass
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(1),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await _run_volumes_clennup()
            assert spy_remove_volume.call_count == len(VOLUMES_TO_CREATE)
            assert len(mock_docker_utils.get_unused_dynamc_sidecar_volumes()) == 0
