# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
import asyncio
import os
from collections.abc import AsyncIterable, AsyncIterator, Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import aioboto3
import aiodocker
import aiofiles
import pytest
from _pytest._py.path import LocalPath
from aiobotocore.session import ClientCreatorContext
from aiodocker import Docker
from aiodocker.types import JSONObject
from botocore.client import Config
from faker import Faker
from models_library.api_schemas_storage.storage_schemas import S3BucketName
from models_library.projects_nodes_io import NodeID, StorageFileID
from moto.server import ThreadedMotoServer
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.file_utils import create_sha256_checksum
from servicelib.logging_utils import _dampen_noisy_loggers
from settings_library.r_clone import DEFAULT_VFS_CACHE_PATH, RCloneSettings
from simcore_sdk.node_ports_common.r_clone_mount import (
    DelegateInterface,
    MountActivity,
    MountRemoteType,
    RCloneMountManager,
)
from simcore_sdk.node_ports_common.r_clone_mount._utils import get_mount_id
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)
from types_aiobotocore_s3 import S3Client

_dampen_noisy_loggers(("botocore", "aiobotocore", "aioboto3", "moto.server"))


@pytest.fixture
def bucket_name() -> S3BucketName:
    return TypeAdapter(S3BucketName).validate_python("osparc-data")


@pytest.fixture
def mock_environment(monkeypatch: pytest.MonkeyPatch, bucket_name: S3BucketName, r_clone_version: str) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "R_CLONE_PROVIDER": "AWS_MOTO",
            "S3_ENDPOINT": "http://172.17.0.1:5000",
            "S3_ACCESS_KEY": "test",
            "S3_BUCKET_NAME": bucket_name,
            "S3_SECRET_KEY": "test",
            "S3_REGION": "us-east-1",
            "R_CLONE_VERSION": r_clone_version,
            "R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_SHOW_DEBUG_LOGS": "1",
        },
    )


@pytest.fixture
def r_clone_settings(mock_environment: EnvVarsDict) -> RCloneSettings:
    return RCloneSettings.create_from_envs()


@pytest.fixture
async def s3_client(r_clone_settings: RCloneSettings, bucket_name: S3BucketName) -> AsyncIterable[S3Client]:
    s3_settings = r_clone_settings.R_CLONE_S3
    session = aioboto3.Session()
    session_client = session.client(
        "s3",
        endpoint_url=f"{s3_settings.S3_ENDPOINT}".replace("moto", "localhost"),
        aws_access_key_id=s3_settings.S3_ACCESS_KEY,
        aws_secret_access_key=s3_settings.S3_SECRET_KEY,
        region_name=s3_settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )
    assert isinstance(session_client, ClientCreatorContext)  # nosec
    async with session_client as client:
        client = cast(S3Client, client)

        await client.create_bucket(Bucket=bucket_name)

        yield client


@pytest.fixture
async def mocked_shutdown() -> AsyncMock:
    return AsyncMock()


class _TestingDelegate(DelegateInterface):
    def __init__(self, vfs_cache_path: Path, mocked_shutdown: AsyncMock) -> None:
        self.vfs_cache_path = vfs_cache_path
        self.mocked_shutdown = mocked_shutdown

    async def get_local_vfs_cache_path(self) -> Path:
        # should normally be /DY_VOLUMES/vfs-cache in the sidecar
        # but for testing it's ok to reuse the local folder since it's not mounted
        return self.vfs_cache_path

    async def get_bind_paths(self, state_path: Path) -> list:
        return [
            {
                "Type": "bind",
                "Source": f"{state_path}",
                "Target": f"{state_path}",
                "BindOptions": {"Propagation": "rshared"},
            },
            {
                "Type": "bind",
                "Source": f"{self.vfs_cache_path}",
                "Target": f"{DEFAULT_VFS_CACHE_PATH}",
                "BindOptions": {"Propagation": "rshared"},
            },
        ]

    async def mount_activity(self, state_path: Path, activity: MountActivity) -> None:
        print(f"⏳ {state_path=} {activity=}")

    async def request_shutdown(self) -> None:
        await self.mocked_shutdown()

    async def create_container(self, config: JSONObject, name: str) -> None:
        async with Docker() as client:
            await client.containers.run(config=config, name=name)

    async def container_inspect(self, container_name: str) -> dict[str, Any]:
        async with Docker() as client:
            existing_container = await client.containers.get(container_name)
            return await existing_container.show()

    async def remove_container(self, container_name: str) -> None:
        async with Docker() as client:
            existing_container = await client.containers.get(container_name)
            await existing_container.delete(force=True)

    async def get_node_address(self) -> str:
        async with Docker() as client:
            system_info = await client.system.info()
            return system_info["Swarm"]["NodeAddr"]


@pytest.fixture
async def r_clone_mount_manager(
    r_clone_settings: RCloneSettings, mocked_shutdown: AsyncMock, vfs_cache_path: Path
) -> AsyncIterator[RCloneMountManager]:
    manager = RCloneMountManager(r_clone_settings, delegate=_TestingDelegate(vfs_cache_path, mocked_shutdown))
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
    return TypeAdapter(StorageFileID).validate_python(f"{faker.uuid4()}/{faker.uuid4()}/mounted-path")


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def moto_server() -> Iterator[None]:
    server = ThreadedMotoServer()
    server.start()
    yield None
    server.stop()


async def _create_random_binary_file(
    file_path: Path,
    file_size: ByteSize,
    chunk_size: int = TypeAdapter(ByteSize).validate_python("1mib"),
) -> None:
    async with aiofiles.open(file_path, mode="wb") as file:
        bytes_written = 0
        while bytes_written < file_size:
            remaining_bytes = file_size - bytes_written
            current_chunk_size = min(chunk_size, remaining_bytes)
            await file.write(os.urandom(current_chunk_size))
            bytes_written += current_chunk_size
        assert bytes_written == file_size


async def _create_file_of_size(target_dir: Path, *, name: str, file_size: ByteSize) -> Path:
    file_path = target_dir / name
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)

    await _create_random_binary_file(file_path, file_size)
    assert file_path.exists()
    assert file_path.stat().st_size == file_size
    return file_path


async def _create_files_in_dir(target_dir: Path, file_count: int, file_size: ByteSize) -> set[str]:
    files = []
    for i in range(file_count):
        file_path = await _create_file_of_size(target_dir, name=f"file_{i}.bin", file_size=file_size)
        files.append(file_path)
    return {x.name for x in files}


async def _get_file_checksums_from_path(
    local_path: Path,
) -> dict[Path, str]:
    checksums = {}
    for dirpath, _, filenames in os.walk(local_path):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            relative_path = file_path.relative_to(local_path)

            async with aiofiles.open(file_path, "rb") as file:
                checksum = await create_sha256_checksum(file)

            checksums[relative_path] = checksum
    return checksums


async def _get_file_checksums_from_s3(
    s3_client: S3Client, bucket_name: S3BucketName, remote_path: StorageFileID
) -> dict[Path, str]:
    response = await s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f"{remote_path}")

    checksums = {}
    for obj in response.get("Contents", []):
        key = obj["Key"]
        file_response = await s3_client.get_object(Bucket=bucket_name, Key=key)
        checksum = await create_sha256_checksum(file_response["Body"])
        relative_path = Path(key).relative_to(Path(remote_path))
        checksums[relative_path] = checksum

    return checksums


async def test_workflow(
    moto_server: None,
    r_clone_mount_manager: RCloneMountManager,
    r_clone_settings: RCloneSettings,
    bucket_name: S3BucketName,
    node_id: NodeID,
    remote_path: StorageFileID,
    local_mount_path: Path,
    index: int,
    s3_client: S3Client,
    mocked_shutdown: AsyncMock,
) -> None:
    await r_clone_mount_manager.ensure_mounted(
        local_mount_path=local_mount_path,
        remote_type=MountRemoteType.S3,
        remote_path=remote_path,
        node_id=node_id,
        index=index,
    )

    # create random test files
    file_count = 5
    file_size = TypeAdapter(ByteSize).validate_python("100kb")
    created_files = await _create_files_in_dir(local_mount_path, file_count, file_size)
    assert len(created_files) == file_count

    # get checksums of local files before unmounting
    local_checksums = await _get_file_checksums_from_path(local_mount_path)
    assert len(local_checksums) == file_count

    # wait for rclone to complete all transfers
    for mount in r_clone_mount_manager._tracked_mounts.values():  # noqa: SLF001
        await mount.wait_for_all_transfers_to_complete()

    # verify data is in S3 with matching checksums and filenames
    s3_checksums = await _get_file_checksums_from_s3(s3_client, bucket_name, remote_path)

    # compare checksums and filenames
    assert len(s3_checksums) == len(local_checksums), "File count mismatch"
    assert set(s3_checksums.keys()) == set(local_checksums.keys()), "Filename mismatch"

    for file_path, local_checksum in local_checksums.items():
        s3_checksum = s3_checksums[file_path]
        assert local_checksum == s3_checksum, (
            f"Checksum mismatch for {file_path}: local={local_checksum}, s3={s3_checksum}"
        )

    await r_clone_mount_manager.ensure_unmounted(local_mount_path=local_mount_path, index=index)

    mocked_shutdown.assert_not_called()


async def test_container_recovers_and_shutdown_is_emitted(
    moto_server: None,
    r_clone_mount_manager: RCloneMountManager,
    node_id: NodeID,
    remote_path: StorageFileID,
    local_mount_path: Path,
    index: int,
    mocked_shutdown: AsyncMock,
) -> None:
    await r_clone_mount_manager.ensure_mounted(
        local_mount_path=local_mount_path,
        remote_type=MountRemoteType.S3,
        remote_path=remote_path,
        node_id=node_id,
        index=index,
    )

    # Get the tracked mount and its container
    mount_id = get_mount_id(local_mount_path, index)
    tracked_mount = r_clone_mount_manager._tracked_mounts[mount_id]  # noqa: SLF001
    container_name = (
        tracked_mount._container_manager._r_clone_container_name  # noqa: SLF001
    )

    # Shutdown the container to trigger the shutdown handler
    async with aiodocker.Docker() as client:
        container = await client.containers.get(container_name)
        await container.stop()

    # wait for the container to recover
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(30),
        wait=wait_fixed(0.1),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            await asyncio.sleep(0)
            mocked_shutdown.assert_called()
