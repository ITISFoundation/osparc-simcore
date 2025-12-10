# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
import os
import re
import secrets
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final, cast

import aioboto3
import aiodocker
import aiofiles
import pytest
from aiobotocore.session import ClientCreatorContext
from aiodocker.networks import DockerNetwork
from botocore.client import Config
from faker import Faker
from models_library.api_schemas_storage.storage_schemas import S3BucketName
from models_library.basic_types import PortInt
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.container_utils import run_command_in_container
from servicelib.file_utils import create_sha256_checksum
from servicelib.logging_utils import _dampen_noisy_loggers
from servicelib.utils import limited_gather
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_ports_common._r_clone_mount import RCloneMountManager, _core
from simcore_sdk.node_ports_common._r_clone_mount._config_provider import (
    MountRemoteType,
)
from simcore_sdk.node_ports_common._r_clone_mount._core import (
    DaemonProcessManager,
)
from types_aiobotocore_s3 import S3Client

_dampen_noisy_loggers(("botocore", "aiobotocore", "aioboto3", "moto.server"))


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
def local_s3_content_path(tmpdir: Path) -> Path:
    # path where s3 are created and then uploaded form
    path = Path(tmpdir) / "copy_to_s3"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def r_clone_local_mount_path(tmpdir: Path) -> Path:
    # where rclone mount will make the files available
    path = Path(tmpdir) / "r_clone_local_mount_path"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def config_path(tmpdir: Path) -> Path:
    # where the configuration path for rclone is found inside the container
    path = Path(tmpdir) / "config_path"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def mock_config_file(config_path: Path, faker: Faker, mocker: MockerFixture) -> None:
    # ensure this returns a path where the config is living which has to be mounted in the container
    # replace context manager with one that writes here
    @asynccontextmanager
    async def config_file(config: str) -> AsyncIterator[str]:
        file_path = config_path / f"{faker.uuid4()}"
        file_path.write_text(config)
        yield f"{file_path}"

        file_path.unlink()

    mocker.patch.object(_core, "config_file", config_file)


_MONITORING_PORT: Final[PortInt] = 5572


@pytest.fixture
async def docker_network() -> AsyncIterable[DockerNetwork]:
    async with aiodocker.Docker() as client:
        network_to_attach = await client.networks.create({"Name": "a_test_network"})
        try:
            yield network_to_attach
        finally:
            await network_to_attach.delete()


@pytest.fixture
async def r_clone_container(
    r_clone_version: str,
    r_clone_local_mount_path: Path,
    config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    docker_network: DockerNetwork,
) -> AsyncIterable[str]:
    async with aiodocker.Docker() as client:
        container = await client.containers.run(
            config={
                "Image": f"rclone/rclone:{r_clone_version}",
                "Entrypoint": ["/bin/sh", "-c", "apk add findutils && sleep 10000"],
                "ExposedPorts": {f"{_MONITORING_PORT}/tcp": {}},
                "HostConfig": {
                    "PortBindings": {
                        f"{_MONITORING_PORT}/tcp": [{"HostPort": f"{_MONITORING_PORT}"}]
                    },
                    "Binds": [
                        f"{r_clone_local_mount_path}:{r_clone_local_mount_path}:rw",
                        f"{config_path}:{config_path}:rw",
                    ],
                    "Devices": [
                        {
                            "PathOnHost": "/dev/fuse",
                            "PathInContainer": "/dev/fuse",
                            "CgroupPermissions": "rwm",
                        }
                    ],
                    "CapAdd": ["SYS_ADMIN"],
                    "SecurityOpt": ["apparmor:unconfined", "seccomp:unconfined"],
                },
            }
        )
        container_inspect = await container.show()

        container_name = container_inspect["Name"][1:]
        monkeypatch.setenv("HOSTNAME", container_name)

        await docker_network.connect({"Container": container.id})

        try:
            yield container.id
        finally:
            await container.delete(force=True)


@pytest.fixture
async def moto_container(docker_network: DockerNetwork) -> AsyncIterable[None]:
    async with aiodocker.Docker() as client:
        container = await client.containers.run(
            config={
                "Image": "motoserver/moto:latest",
                "ExposedPorts": {"5000/tcp": {}},
                "HostConfig": {
                    "PortBindings": {"5000/tcp": [{"HostPort": "5000"}]},
                },
                "Env": ["MOTO_PORT=5000"],
            },
            name="moto",
        )
        await docker_network.connect({"Container": container.id})

        try:
            yield None
        finally:
            await container.delete(force=True)


async def test_daemon_container_process(r_clone_container: str):
    container_process = DaemonProcessManager("sleep 10000")
    await container_process.start()
    assert container_process.pid

    ps_command = "ps -o pid,stat,comm"
    result = await container_process._run_in_container(ps_command)  # noqa: SLF001
    assert f"{container_process.pid} S" in result  # check sleeping

    await container_process.stop()
    await container_process._run_in_container(ps_command)  # noqa: SLF001
    assert f"{container_process.pid} Z" not in result  # check killed


@pytest.fixture
def mock_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "R_CLONE_PROVIDER": "AWS_MOTO",
            "S3_ENDPOINT": "http://moto:5000",
            "S3_ACCESS_KEY": "test",
            "S3_BUCKET_NAME": "test",
            "S3_SECRET_KEY": "test",
            "S3_REGION": "us-east-1",
        },
    )


@pytest.fixture
def r_clone_settings(mock_environment: EnvVarsDict) -> RCloneSettings:
    return RCloneSettings.create_from_envs()


@pytest.fixture
def remote_path() -> Path:
    return Path("test")


@pytest.fixture
async def s3_client(r_clone_settings: RCloneSettings) -> AsyncIterable[S3Client]:
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
        yield client


@pytest.fixture
def bucket_name(r_clone_settings: RCloneSettings) -> S3BucketName:
    return TypeAdapter(S3BucketName).validate_python(
        r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME
    )


def _secure_randint(a: int, b: int) -> int:
    return a + secrets.randbelow(b - a + 1)


_DEFAULT_CHUCNK_SIZE: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("1kb")


async def _get_random_file(
    faker: Faker,
    *,
    store_to: Path,
    file_size: ByteSize,
    chunk_size: ByteSize = _DEFAULT_CHUCNK_SIZE,
) -> Path:
    # creates a file in a path and returns it's hash
    # generate a random file of size X and a random path inside the directory

    path_in_folder = Path(
        faker.file_path(depth=_secure_randint(0, 5), extension="bin")
    ).relative_to("/")
    file_path = store_to / path_in_folder

    # ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    assert file_path.parent.exists()

    async with aiofiles.open(file_path, "wb") as file:
        written = 0
        while written < file_size:
            to_write = min(chunk_size, file_size - written)
            chunk = os.urandom(to_write)
            await file.write(chunk)
            written += to_write

    return path_in_folder


def _get_random_file_size() -> ByteSize:
    return TypeAdapter(ByteSize).validate_python(f"{_secure_randint(1,1024)}Kb")


@pytest.fixture
async def create_files_in_s3(
    r_clone_settings: RCloneSettings,
    moto_container: None,
    s3_client: S3Client,
    bucket_name: S3BucketName,
    faker: Faker,
    remote_path: Path,
    local_s3_content_path: Path,
) -> AsyncIterable[None]:

    await s3_client.create_bucket(Bucket=bucket_name)

    async def _create_file() -> None:
        path_in_folder = await _get_random_file(
            faker,
            store_to=local_s3_content_path,
            file_size=_get_random_file_size(),
        )
        file_path = local_s3_content_path / path_in_folder
        assert file_path.exists()
        await s3_client.upload_file(
            Filename=f"{file_path}",
            Bucket=bucket_name,
            Key=f"{remote_path/path_in_folder}",
        )

    files_to_create = _secure_randint(5, 20)
    await limited_gather(*[_create_file() for _ in range(files_to_create)], limit=5)

    yield None

    files_in_bucket = await s3_client.list_objects_v2(Bucket=bucket_name)

    await limited_gather(
        *[
            s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
            for obj in files_in_bucket.get("Contents", [])
        ],
        limit=10,
    )

    # check all content form s3 was removed
    files_in_bucket = await s3_client.list_objects_v2(Bucket=bucket_name)
    assert files_in_bucket.get("Contents", []) == []


@pytest.fixture
def mock_rc_port_with_default(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_sdk.node_ports_common._r_clone_mount._core.unused_port",
        return_value=_MONITORING_PORT,
    )


@pytest.fixture
def vfs_cache_path(tmpdir: Path) -> Path:
    # path inside the docker container where the vfs cache will be stored
    # for tests this can be just placed in the tmp directory ?
    # TODO: for better tests it's better that is mounted as a volume
    return Path("/tmp/rclone_cache")  # noqa: S108


@pytest.fixture
async def single_mount_r_clone_mount_manager(
    mock_rc_port_with_default: None,
    r_clone_container: str,
    mock_config_file: None,
    r_clone_settings: RCloneSettings,
    vfs_cache_path: Path,
) -> AsyncIterable[RCloneMountManager]:
    r_clone_mount_manager = RCloneMountManager(r_clone_settings, vfs_cache_path)

    yield r_clone_mount_manager

    await r_clone_mount_manager.teardown()


async def _get_file_checksums_from_local_path(
    local_s3_content_path: Path,
) -> dict[Path, str]:
    local_checksums = {}
    for dirpath, _, filenames in os.walk(local_s3_content_path):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            relative_path = file_path.relative_to(local_s3_content_path)

            async with aiofiles.open(file_path, "rb") as file:
                checksum = await create_sha256_checksum(file)

            local_checksums[relative_path] = checksum
    return local_checksums


async def _get_file_checksums_from_container(
    remote_path: Path,
    r_clone_container: str,
    bucket_name: S3BucketName,
) -> dict[Path, str]:
    remote_checksum_and_files = await run_command_in_container(
        r_clone_container,
        command=f"find {remote_path} -type f -exec sha256sum {{}} \\;",
        timeout=30,
    )

    def _parse_entry(entry: str) -> tuple[Path, str]:
        checksum, file_path = entry.strip().split()
        relative_path = (
            Path(file_path).relative_to(remote_path).relative_to(Path(bucket_name))
        )
        return relative_path, checksum

    return dict(
        [_parse_entry(x) for x in remote_checksum_and_files.strip().split("\n")]
    )


async def _get_files_from_s3(
    s3_client: S3Client,
    bucket_name: S3BucketName,
) -> dict[Path, str]:
    """Download files from S3 and return their SHA256 checksums."""
    files_in_bucket = await s3_client.list_objects_v2(Bucket=bucket_name)

    async def _get_file_checksum(key: str) -> tuple[Path, str]:
        response = await s3_client.get_object(Bucket=bucket_name, Key=key)
        checksum = await create_sha256_checksum(response["Body"])
        return Path(key).relative_to(Path(bucket_name)), checksum

    results = await limited_gather(
        *[
            _get_file_checksum(obj["Key"])
            for obj in files_in_bucket.get("Contents", [])
        ],
        limit=10,
    )

    return dict(results)


async def _assert_local_content_in_s3(
    s3_client: S3Client,
    bucket_name: S3BucketName,
    local_s3_content_path: Path,
) -> None:
    files_local_folder = await _get_file_checksums_from_local_path(
        local_s3_content_path
    )
    files_from_s3 = await _get_files_from_s3(s3_client, bucket_name)

    assert files_local_folder == files_from_s3


async def _assert_same_files_in_all_places(
    s3_client: S3Client,
    bucket_name: S3BucketName,
    r_clone_container: str,
    r_clone_local_mount_path: Path,
) -> None:
    files_from_container = await _get_file_checksums_from_container(
        r_clone_local_mount_path, r_clone_container, bucket_name
    )
    files_from_s3 = await _get_files_from_s3(s3_client, bucket_name)
    assert files_from_container == files_from_s3


async def _change_file_in_container(remote_path: Path, r_clone_container: str) -> None:
    await run_command_in_container(
        r_clone_container,
        command=f"dd if=/dev/urandom of={remote_path} bs={_get_random_file_size()} count=1",
        timeout=30,
    )


async def test_tracked_mount_waits_for_files_before_finalizing(
    create_files_in_s3: None,
    single_mount_r_clone_mount_manager: RCloneMountManager,
    r_clone_local_mount_path: Path,
    # maybe drop
    s3_client: S3Client,
    bucket_name: S3BucketName,
    r_clone_container: str,
    local_s3_content_path: Path,
    remote_path: Path,
):
    await single_mount_r_clone_mount_manager.start_mount(
        MountRemoteType.S3, remote_path, r_clone_local_mount_path
    )

    await _assert_local_content_in_s3(s3_client, bucket_name, local_s3_content_path)

    def _get_random_file_in_container() -> Path:
        return (
            r_clone_local_mount_path
            / bucket_name
            / secrets.choice(
                [x for x in local_s3_content_path.rglob("*") if x.is_file()]
            ).relative_to(local_s3_content_path)
        )

    # change and check all is the same
    files_to_change = {_get_random_file_in_container() for _ in range(15)}
    await limited_gather(
        *[_change_file_in_container(x, r_clone_container) for x in files_to_change],
        limit=10,
    )

    await single_mount_r_clone_mount_manager.wait_for_transfers_to_complete(
        r_clone_local_mount_path
    )
    await _assert_same_files_in_all_places(
        s3_client,
        bucket_name,
        r_clone_container,
        r_clone_local_mount_path,
    )

    await single_mount_r_clone_mount_manager.stop_mount(r_clone_local_mount_path)


# TODO: we need a mode to check if rclone mount properly resumes the mounting in case of crash and restart
# we need a test for this one
