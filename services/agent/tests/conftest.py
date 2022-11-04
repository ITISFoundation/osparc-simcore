# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from pathlib import Path
from typing import AsyncIterator, Iterable, Iterator
from uuid import uuid4

import aiodocker
import pytest
import simcore_service_agent
from _pytest.logging import LogCaptureFixture
from aiodocker.volumes import DockerVolume
from models_library.basic_types import BootModeEnum
from moto.server import ThreadedMotoServer
from pydantic import HttpUrl, parse_obj_as
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from settings_library.r_clone import S3Provider
from simcore_service_agent.core.settings import ApplicationSettings

pytestmark = pytest.mark.asyncio

pytest_plugins = [
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "agent"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_agent"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_agent.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def swarm_stack_name() -> str:
    return "test-simcore"


@pytest.fixture
def study_id() -> str:
    return f"{uuid4()}"


@pytest.fixture
def node_uuid() -> str:
    return f"{uuid4()}"


@pytest.fixture
def run_id() -> str:
    return f"{uuid4()}"


@pytest.fixture
def bucket() -> str:
    return f"test-bucket-{uuid4()}"


@pytest.fixture
def used_volume_path(tmp_path: Path) -> Path:
    return tmp_path / "used_volume"


@pytest.fixture
def unused_volume_path(tmp_path: Path) -> Path:
    return tmp_path / "unused_volume"


def _get_source(run_id: str, node_uuid: str, volume_path: Path) -> str:
    reversed_path = f"{volume_path}"[::-1].replace("/", "_")
    return f"dyv_{run_id}_{node_uuid}_{reversed_path}"


@pytest.fixture
async def unused_volume(
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
    unused_volume_path: Path,
) -> AsyncIterator[DockerVolume]:

    async with aiodocker.Docker() as docker_client:
        source = _get_source(run_id, node_uuid, unused_volume_path)
        volume = await docker_client.volumes.create(
            {
                "Name": source,
                "Labels": {
                    "node_uuid": node_uuid,
                    "run_id": run_id,
                    "source": source,
                    "study_id": study_id,
                    "swarm_stack_name": swarm_stack_name,
                    "user_id": "1",
                },
            }
        )

        # attach to volume and create some files!!!

        yield volume

        try:
            await volume.delete()
        except aiodocker.DockerError:
            pass


@pytest.fixture
async def used_volume(
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
    used_volume_path: Path,
) -> AsyncIterator[DockerVolume]:
    async with aiodocker.Docker() as docker_client:
        source = _get_source(run_id, node_uuid, used_volume_path)
        volume = await docker_client.volumes.create(
            {
                "Name": source,
                "Labels": {
                    "node_uuid": node_uuid,
                    "run_id": run_id,
                    "source": source,
                    "study_id": study_id,
                    "swarm_stack_name": swarm_stack_name,
                    "user_id": "1",
                },
            }
        )

        container = await docker_client.containers.run(
            config={
                "Cmd": ["/bin/ash", "-c", "sleep 10000"],
                "Image": "alpine:latest",
                "HostConfig": {"Binds": [f"{volume.name}:{used_volume_path}"]},
            },
            name=f"using_volume_{volume.name}",
        )
        await container.start()

        yield volume

        await container.delete(force=True)
        await volume.delete()


@pytest.fixture
def env(monkeypatch: MonkeyPatch, mocked_s3_server_url: HttpUrl, bucket: str) -> None:
    mock_dict = {
        "LOGLEVEL": "DEBUG",
        "SC_BOOT_MODE": BootModeEnum.DEBUG,
        "AGENT_VOLUMES_CLEANUP_S3_ENDPOINT": mocked_s3_server_url,
        "AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY": "xxx",
        "AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY": "xxx",
        "AGENT_VOLUMES_CLEANUP_S3_BUCKET": bucket,
        "AGENT_VOLUMES_CLEANUP_S3_PROVIDER": S3Provider.MINIO,
    }
    for key, value in mock_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def settings(env: None) -> ApplicationSettings:
    return ApplicationSettings.create_from_envs()


@pytest.fixture()
def caplog_info_debug(caplog: LogCaptureFixture) -> Iterable[LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


@pytest.fixture
def mocked_s3_server_url() -> Iterator[HttpUrl]:
    """
    For download links, the in-memory moto.mock_s3() does not suffice since
    we need an http entrypoint
    """
    # http://docs.getmoto.org/en/latest/docs/server_mode.html#start-within-python
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=9000)

    # pylint: disable=protected-access
    endpoint_url = parse_obj_as(HttpUrl, f"http://{server._ip_address}:{server._port}")

    print(f"--> started mock S3 server on {endpoint_url}")
    server.start()

    yield endpoint_url

    server.stop()
    print(f"<-- stopped mock S3 server on {endpoint_url}")
