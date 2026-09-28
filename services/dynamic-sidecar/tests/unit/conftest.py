# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
import multiprocessing
from collections.abc import AsyncIterable, AsyncIterator, Callable
from multiprocessing.queues import Queue
from threading import Barrier, Thread
from typing import Final
from unittest.mock import AsyncMock

import pytest
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager as ASGILifespanManager
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pydantic import PositiveFloat
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_dynamic_sidecar.core.application import AppState, create_app
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_down,
)
from simcore_service_dynamic_sidecar.core.docker_utils import docker_client
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.notifications._notifications_ports import (
    PortNotifier,
)
from tenacity import retry
from tenacity.after import after_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)

_CONCURRENT_RUN_TIMEOUT_S: Final[float] = 10


#
# APP and CLIENT fixtures
#
#  In this context by default all external services are
#  mocked (e.g. registry, rabbitmq, ...)
#
#


@pytest.fixture
def app(mock_environment: EnvVarsDict, mock_registry_service: AsyncMock) -> FastAPI:
    """creates app with registry and rabbitMQ services mocked"""
    return create_app()


@pytest.fixture
def max_response_time() -> int:
    """sets client timeout: can be used to detect SLOW handlers"""
    return 60


@pytest.fixture
async def initialized_app(app: FastAPI) -> AsyncIterable[FastAPI]:
    try:
        AppState(app)
    except ValueError:
        async with ASGILifespanManager(app):
            yield app
    else:
        yield app


#
# DOCKER Fixtures
#
#


@pytest.fixture
def test_client(initialized_app: FastAPI, max_response_time: int) -> TestClient:
    return TestClient(initialized_app, timeout=max_response_time)


@pytest.fixture
async def ensure_external_volumes(
    initialized_app: FastAPI,
) -> AsyncIterator[tuple[DockerVolume, ...]]:
    """ensures inputs and outputs volumes for the service are present

    Emulates creation of volumes by the directorv2 when it spawns the dynamic-sidecar service
    """
    app_state = AppState(initialized_app)
    volume_labels_source = [
        app_state.mounted_volumes.volume_name_inputs,
        app_state.mounted_volumes.volume_name_outputs,
        *list(app_state.mounted_volumes.volume_name_state_paths()),
    ]

    async with docker_client() as docker:
        volumes = await asyncio.gather(
            *[
                docker.volumes.create(
                    {
                        "Labels": {
                            "source": source,
                            "run_id": app_state.settings.DY_SIDECAR_RUN_ID,
                        }
                    }
                )
                for source in volume_labels_source
            ]
        )

        yield tuple(volumes)

        @retry(
            wait=wait_fixed(1),
            stop=stop_after_delay(3),
            reraise=True,
            after=after_log(logger, logging.WARNING),
        )
        async def _delete(volume):
            # Occasionally might raise because volumes are mounted to closing containers
            await volume.delete()

        deleted = await asyncio.gather(*(_delete(volume) for volume in volumes), return_exceptions=True)
        assert not [r for r in deleted if isinstance(r, Exception)]


@pytest.fixture
async def cleanup_containers(initialized_app: FastAPI) -> AsyncIterator[None]:
    app_state = AppState(initialized_app)

    yield
    # run docker compose down here

    if app_state.compose_spec is None:
        # if no compose-spec is stored skip this operation
        return

    await docker_compose_down(app_state.compose_spec, app_state.settings)


@pytest.fixture
def port_notifier(app: FastAPI) -> PortNotifier:
    settings: ApplicationSettings = app.state.settings
    return PortNotifier(
        app,
        settings.DY_SIDECAR_USER_ID,
        settings.DY_SIDECAR_PROJECT_ID,
        settings.DY_SIDECAR_NODE_ID,
    )


@pytest.fixture
def mock_ensure_read_permissions_on_user_service_data(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks.ensure_read_permissions_on_user_service_data",
    )


@pytest.fixture
def health_check_queue() -> Queue[int | None]:
    return multiprocessing.Queue()


@pytest.fixture
def heart_beat_interval_s() -> PositiveFloat:
    return 0.01


@pytest.fixture
def run_concurrently() -> Callable[[list[Callable[[], None]]], list[BaseException]]:
    """runs the given callables in threads started at the same time and returns the raised errors"""

    def _(targets: list[Callable[[], None]]) -> list[BaseException]:
        errors: list[BaseException] = []
        start_together = Barrier(len(targets))

        def _run(target: Callable[[], None]) -> None:
            start_together.wait(timeout=_CONCURRENT_RUN_TIMEOUT_S)
            try:
                target()
            except BaseException as exc:  # pylint: disable=broad-except
                errors.append(exc)

        threads = [Thread(target=_run, args=(target,)) for target in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=_CONCURRENT_RUN_TIMEOUT_S)

        assert not [t for t in threads if t.is_alive()], "threads did not complete (deadlock?)"
        return errors

    return _
