# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import os
import subprocess
import sys
from typing import AsyncGenerator
from unittest import mock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.application import assemble_application
from simcore_service_dynamic_sidecar.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.shared_handlers import write_file_and_run_command
from simcore_service_dynamic_sidecar.storage import SharedStore


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
    stored_compose_content = shared_store.get_spec()

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


@pytest.fixture(autouse=True)
async def monkey_patch_asyncio_subprocess(mocker) -> None:
    # TODO: The below bug is not allowing me to fully test,
    # mocking and waiting for an update
    # https://bugs.python.org/issue35621
    # this issue was patched in 3.8, no need
    if sys.version_info.major == 3 and sys.version_info.minor >= 8:
        raise RuntimeError(
            "Issue no longer present in this version of python, "
            "please remote this mock on python >= 3.8"
        )

    async def create_subprocess_exec(*command, **extra_params):
        class MockResponse:
            def __init__(self, command, **kwargs):
                self.proc = subprocess.Popen(command, **extra_params)

            async def communicate(self):
                return self.proc.communicate()

            @property
            def returncode(self):
                return self.proc.returncode

        mock_response = MockResponse(command, **extra_params)

        return mock_response

    mocker.patch("asyncio.create_subprocess_exec", side_effect=create_subprocess_exec)


@pytest.fixture
def mock_containers_get(mocker) -> None:
    async def mock_get(*args, **kwargs):
        raise aiodocker.exceptions.DockerError(
            status="mock", data=dict(message="aiodocker_mocked_error")
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)
