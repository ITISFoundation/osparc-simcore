# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import contextlib
import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import aiodocker
import pytest
from _pytest._py.path import LocalPath
from aiodocker.types import JSONObject
from faker import Faker
from models_library.api_schemas_storage.storage_schemas import S3BucketName
from models_library.basic_types import PortInt
from models_library.projects_nodes_io import NodeID, StorageFileID
from moto.server import ThreadedMotoServer
from pydantic import ByteSize, NonNegativeInt, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.logging_utils import _dampen_noisy_loggers
from settings_library.r_clone import DEFAULT_VFS_CACHE_PATH, RCloneSettings
from simcore_sdk.node_ports_common.r_clone_mount import (
    GetBindPathsProtocol,
    MountActivity,
    MountRemoteType,
    RCloneMountManager,
)
from simcore_sdk.node_ports_common.r_clone_mount._container import (
    RemoteControlHttpClient,
)
from simcore_sdk.node_ports_common.r_clone_mount._docker_utils import (
    _get_config as original_get_config,
)

_dampen_noisy_loggers(("botocore", "aiobotocore", "aioboto3", "moto.server"))


@pytest.fixture
def bucket_name() -> S3BucketName:
    return TypeAdapter(S3BucketName).validate_python("osparc-data")


@pytest.fixture
def r_clone_version(package_dir: Path) -> str:
    install_rclone_bash = (
        (package_dir / ".." / ".." / ".." / "..").resolve()
        / "scripts"
        / "install_rclone.bash"
    )
    assert install_rclone_bash.exists()

    match = re.search(r'R_CLONE_VERSION="([\d.]+)"', install_rclone_bash.read_text())
    assert match
    return match.group(1)


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch, bucket_name: S3BucketName, r_clone_version: str
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "R_CLONE_PROVIDER": "AWS_MOTO",
            "S3_ENDPOINT": "http://127.0.0.1:5000",
            "S3_ACCESS_KEY": "test",
            "S3_BUCKET_NAME": bucket_name,
            "S3_SECRET_KEY": "test",
            "S3_REGION": "us-east-1",
            "R_CLONE_VERSION": r_clone_version,
            "R_CLONE_MOUNT_CONTAINER_SHOW_DEBUG_LOGS": "1",
        },
    )


@pytest.fixture
def r_clone_settings(mock_environment: EnvVarsDict) -> RCloneSettings:
    return RCloneSettings.create_from_envs()


@pytest.fixture
async def r_clone_mount_manager(
    r_clone_settings: RCloneSettings,
) -> AsyncIterator[RCloneMountManager]:

    # TODO: maybe put this into a fixture
    async def do_nothing() -> None:
        pass

    manager = RCloneMountManager(r_clone_settings, handler_request_shutdown=do_nothing)
    await manager.setup()

    yield manager

    await manager.teardown()


@pytest.fixture
def local_mount_path(tmpdir: LocalPath) -> Path:
    local_mount_path = Path(tmpdir) / "local_mount_path"
    local_mount_path.mkdir(parents=True, exist_ok=True)
    return local_mount_path


@pytest.fixture
def vfs_cache_path(tmpdir: LocalPath) -> Path:
    vfs_cache_path = Path(tmpdir) / "vfs_cache_path"
    vfs_cache_path.mkdir(parents=True, exist_ok=True)
    return vfs_cache_path


@pytest.fixture
def index() -> int:
    return 0


@pytest.fixture
def remote_path(faker: Faker) -> StorageFileID:
    return TypeAdapter(StorageFileID).validate_python(
        f"{faker.uuid4()}/{faker.uuid4()}/mounted-path"
    )


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def moto_server() -> Iterator[None]:
    """Start moto S3 server on port 5000"""
    server = ThreadedMotoServer(port="5000")
    server.start()
    yield None
    server.stop()


@pytest.fixture
async def mocked_self_container(mocker: MockerFixture) -> AsyncIterator[None]:
    # start the simplest lightweight container that sleeps forever
    async with aiodocker.Docker() as client:
        container = await client.containers.run(
            config={"Image": "alpine:latest", "Cmd": ["sleep", "infinity"]}
        )

        mocker.patch(
            "simcore_sdk.node_ports_common.r_clone_mount._docker_utils._get_self_container_id",
            return_value=container.id,
        )

        yield None

        # remove started container
        with contextlib.suppress(aiodocker.exceptions.DockerError):
            await container.delete(force=True)


@pytest.fixture
async def mocked_r_clone_container_config(mocker: MockerFixture) -> None:

    async def _patched_get_config(
        command: str,
        r_clone_version: str,
        rc_port: PortInt,
        r_clone_network_name: str,
        local_mount_path: Path,
        memory_limit: ByteSize,
        nano_cpus: NonNegativeInt,
        handler_get_bind_paths: GetBindPathsProtocol,
    ) -> JSONObject:
        config = await original_get_config(
            command,
            r_clone_version,
            rc_port,
            r_clone_network_name,
            local_mount_path,
            memory_limit,
            nano_cpus,
            handler_get_bind_paths,
        )
        # Add port forwarding to access from host
        config["HostConfig"]["PortBindings"] = {
            f"{rc_port}/tcp": [{"HostPort": str(rc_port)}]
        }
        config["HostConfig"]["NetworkMode"] = "host"
        return config

    mocker.patch(
        "simcore_sdk.node_ports_common.r_clone_mount._docker_utils._get_config",
        side_effect=_patched_get_config,
    )

    # Patch the rc_host to use localhost instead of container name

    original_init = RemoteControlHttpClient.__init__

    def _patched_init(self, rc_host: str, rc_port: PortInt, *args, **kwargs) -> None:
        # Replace container hostname with localhost for host access
        original_init(self, "localhost", rc_port, *args, **kwargs)

    mocker.patch.object(
        RemoteControlHttpClient,
        "__init__",
        _patched_init,
    )


async def _handle_mount_activity(state_path: Path, activity: MountActivity) -> None:
    print(f"⏳ {state_path=} {activity=}")


async def test_manager(
    moto_server: None,
    mocked_r_clone_container_config: None,
    mocked_self_container: None,
    r_clone_mount_manager: RCloneMountManager,
    node_id: NodeID,
    remote_path: StorageFileID,
    local_mount_path: Path,
    vfs_cache_path: Path,
    index: int,
) -> None:

    async def _get_bind_paths_protocol(state_path: Path) -> list[Path]:
        # no need to add bind mount vfs cache for testing
        return [
            {"Type": "bind", "Source": f"{state_path}", "Target": f"{state_path}"},
            {
                "Type": "bind",
                "Source": f"{vfs_cache_path}",
                "Target": f"{DEFAULT_VFS_CACHE_PATH}",
                "BindOptions": {"Propagation": "rshared"},
            },
        ]

    await r_clone_mount_manager.ensure_mounted(
        local_mount_path=local_mount_path,
        remote_type=MountRemoteType.S3,
        remote_path=remote_path,
        node_id=node_id,
        index=index,
        handler_get_bind_paths=_get_bind_paths_protocol,
        handler_mount_activity=_handle_mount_activity,
    )

    await r_clone_mount_manager.ensure_unmounted(
        local_mount_path=local_mount_path, index=index
    )
