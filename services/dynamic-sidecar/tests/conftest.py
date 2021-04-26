# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import os
import sys
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest import mock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.application import assemble_application
from simcore_service_dynamic_sidecar.models.domains.shared_store import SharedStore
from simcore_service_dynamic_sidecar.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.shared_handlers import write_file_and_run_command


@pytest.fixture(scope="module", autouse=True)
def app() -> FastAPI:
    with mock.patch.dict(
        os.environ,
        {
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_compose_namespace": "test-space",
            "DYNAMIC_SIDECAR_docker_compose_down_timeout": "15",
        },
    ):
        return assemble_application()


@pytest.fixture
async def test_client(app: FastAPI) -> TestClient:
    async with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
async def cleanup_containers(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    # run docker compose down here

    shared_store: SharedStore = app.state.shared_store
    stored_compose_content = shared_store.compose_spec

    if stored_compose_content is None:
        # if no compose-spec is stored skip this operation
        return

    settings: DynamicSidecarSettings = app.state.settings
    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --remove-orphans -t {stop_and_remove_timeout}"
    )
    await write_file_and_run_command(
        settings=settings,
        file_content=stored_compose_content,
        command=command,
        command_timeout=5.0,
    )


@pytest.fixture
def mock_containers_get(mocker: MockerFixture) -> None:
    async def mock_get(*args: str, **kwargs: Any) -> None:
        raise aiodocker.exceptions.DockerError(
            status="mock", data=dict(message="aiodocker_mocked_error")
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)


@pytest.fixture
def tests_dir() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
