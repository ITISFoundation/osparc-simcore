# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import os
from typing import Generator
from unittest import mock

import pytest
from httpx import AsyncClient
from simcore_service_service_sidecar.application import assemble_application


@pytest.fixture()
def mock_env_vars() -> Generator[None, None, None]:
    with mock.patch.dict(
        os.environ,
        {
            "SC_BOOT_MODE": "development",
            "SERVICE_SIDECAR_compose_namespace": "test-space",
            "SERVICE_SIDECAR_docker_compose_down_timeout": "15",
        },
    ):
        yield None


@pytest.fixture()
async def async_client(mock_env_vars: None) -> AsyncClient:
    app = assemble_application()
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client
