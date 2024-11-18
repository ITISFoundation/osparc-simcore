# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from pathlib import Path

import aiodocker
import pytest

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.docker_swarm",
]


@pytest.fixture(scope="session")
def package_dir(osparc_simcore_services_dir: Path):
    package_folder = osparc_simcore_services_dir / "osparc-gateway-server"
    assert package_folder.exists()
    return package_folder


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client
