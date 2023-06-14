# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from pathlib import Path
from typing import AsyncIterator, Iterable, Iterator
from uuid import UUID, uuid4

import aiodocker
import pytest
import simcore_service_agent
from aiodocker.volumes import DockerVolume
from faker import Faker
from models_library.basic_types import BootModeEnum
from moto.server import ThreadedMotoServer
from pydantic import HttpUrl, parse_obj_as
from pytest import LogCaptureFixture, MonkeyPatch
from servicelib.sidecar_volumes import VolumeUtils
from settings_library.r_clone import S3Provider
from simcore_service_agent.core.settings import ApplicationSettings

pytestmark = pytest.mark.asyncio

pytest_plugins = [
    "pytest_simcore.aws_services",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
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
def legacy_shared_store_only_volume_states(project_slug_dir: Path) -> Path:
    data_dir = project_slug_dir / "tests" / "data"
    assert data_dir.exists()
    path = data_dir / "legacy_shared_store_only_volume_states.json"
    assert path.exists()
    return path


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


@pytest.fixture
async def unused_volume(
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
    unused_volume_path: Path,
) -> AsyncIterator[DockerVolume]:
    async with aiodocker.Docker() as docker_client:
        source = VolumeUtils.get_source(
            unused_volume_path, UUID(node_uuid), UUID(run_id)
        )
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
        source = VolumeUtils.get_source(used_volume_path, UUID(node_uuid), UUID(run_id))
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
def env(
    monkeypatch: MonkeyPatch,
    mocked_s3_server_url: HttpUrl,
    bucket: str,
    swarm_stack_name: str,
    faker: Faker,
) -> None:
    mock_dict = {
        "LOGLEVEL": "DEBUG",
        "SC_BOOT_MODE": BootModeEnum.DEBUG,
        "AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME": swarm_stack_name,
        "AGENT_VOLUMES_CLEANUP_S3_ENDPOINT": mocked_s3_server_url,
        "AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY": "xxx",
        "AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY": "xxx",
        "AGENT_VOLUMES_CLEANUP_S3_BUCKET": bucket,
        "AGENT_VOLUMES_CLEANUP_S3_PROVIDER": S3Provider.MINIO,
        "AGENT_DOCKER_NODE_ID": f"{faker.uuid4()}",
    }
    for key, value in mock_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def settings(env: None) -> ApplicationSettings:
    return ApplicationSettings.create_from_envs()


@pytest.fixture()
def caplog_debug(caplog: LogCaptureFixture) -> Iterable[LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


@pytest.fixture(scope="module")
def mocked_s3_server_url(mocked_s3_server: ThreadedMotoServer) -> Iterator[HttpUrl]:
    # pylint: disable=protected-access
    endpoint_url = parse_obj_as(
        HttpUrl, f"http://{mocked_s3_server._ip_address}:{mocked_s3_server._port}"
    )
    yield endpoint_url
