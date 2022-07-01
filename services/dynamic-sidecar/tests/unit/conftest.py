# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
from typing import AsyncIterable, AsyncIterator
from unittest.mock import AsyncMock

import pytest
from aiodocker.volumes import DockerVolume
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.core.application import AppState, create_app
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    _write_file_and_run_command,
)
from simcore_service_dynamic_sidecar.core.docker_utils import docker_client
from tenacity import retry
from tenacity.after import after_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


#
# APP and CLIENT fixtures
#
#  In this context by default all external services are
#  mocked (e.g. registry, rabbitmq, ...)
#
#


@pytest.fixture
def mock_registry_service(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.core.utils._is_registry_reachable",
        autospec=True,
    )


@pytest.fixture
def mock_core_rabbitmq(mocker: MockerFixture) -> dict[str, AsyncMock]:
    """mocks simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ member functions"""
    return {
        "connect": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.connect",
            return_value=None,
            autospec=True,
        ),
        "send_event_reload_iframe": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.send_event_reload_iframe",
            return_value=None,
            autospec=True,
        ),
        "post_log_message": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.post_log_message",
            return_value=None,
            autospec=True,
        ),
        "close": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.close",
            return_value=None,
            autospec=True,
        ),
    }


@pytest.fixture
def app(
    mock_environment: None,
    mock_registry_service: AsyncMock,
    mock_core_rabbitmq: dict[str, AsyncMock],
) -> FastAPI:
    """creates app with registry and rabbitMQ services mocked"""
    app = create_app()
    return app


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterable[TestClient]:
    async with TestClient(app) as client:
        yield client


#
# DOCKER Fixtures
#
#


@pytest.fixture
async def ensure_external_volumes(
    app: FastAPI,
) -> AsyncIterator[tuple[DockerVolume]]:
    """ensures inputs and outputs volumes for the service are present

    Emulates creation of volumes by the directorv2 when it spawns the dynamic-sidecar service
    """
    app_state = AppState(app)
    volume_labels_source = [
        app_state.mounted_volumes.volume_name_inputs,
        app_state.mounted_volumes.volume_name_outputs,
    ] + list(app_state.mounted_volumes.volume_name_state_paths())

    async with docker_client() as docker:

        volumes = await asyncio.gather(
            *[
                docker.volumes.create(
                    {
                        "Labels": {
                            "source": source,
                            "run_id": f"{app_state.settings.DY_SIDECAR_RUN_ID}",
                        }
                    }
                )
                for source in volume_labels_source
            ]
        )

        #
        # docker volume ls --format "{{.Name}} {{.Labels}}" | grep run_id | awk '{print $1}')
        #
        #
        # Example
        #   {
        #     "CreatedAt": "2022-06-23T03:22:08+02:00",
        #     "Driver": "local",
        #     "Labels": {
        #         "run_id": "f7c1bd87-4da5-4709-9471-3d60c8a70639",
        #         "source": "dy-sidecar_e3e70682-c209-4cac-a29f-6fbed82c07cd_data_dir_2"
        #     },
        #     "Mountpoint": "/var/lib/docker/volumes/22bfd79a50eb9097d45cc946736cb66f3670a2fadccb62a77ffbe5e1d88f0034/_data",
        #     "Name": "22bfd79a50eb9097d45cc946736cb66f3670a2fadccb62a77ffbe5e1d88f0034",
        #     "Options": null,
        #     "Scope": "local",
        #     "CreatedTime": 1655947328000,
        #     "Containers": {}
        #   }

        yield volumes

        @retry(
            wait=wait_fixed(1),
            stop=stop_after_delay(3),
            reraise=True,
            after=after_log(logger, logging.WARNING),
        )
        async def _delete(volume):
            # Ocasionally might raise because volumes are mount to closing containers
            await volume.delete()

        deleted = await asyncio.gather(
            *(_delete(volume) for volume in volumes), return_exceptions=True
        )
        assert not [r for r in deleted if isinstance(r, Exception)]


@pytest.fixture
async def cleanup_containers(app: FastAPI) -> AsyncIterator[None]:

    app_state = AppState(app)

    yield
    # run docker compose down here

    if app_state.shared_store.compose_spec is None:
        # if no compose-spec is stored skip this operation
        return

    command = (
        'docker-compose --project-name {project} --file "{file_path}" '
        "down --remove-orphans --timeout {stop_and_remove_timeout}"
    )
    await _write_file_and_run_command(
        settings=app_state.settings,
        file_content=app_state.shared_store.compose_spec,
        command=command,
        command_timeout=5.0,
    )
